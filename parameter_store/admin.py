###############################################################################
# Copyright 2024 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################
from typing import TYPE_CHECKING

import unfold.admin as uadmin
import unfold.sites as usites
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as AuthGroupModel
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin

from .admin_inlines import (
    ClusterDataInline,
    ClusterFleetLabelsInline,
    ClusterIntentInline,
    ClusterTagInline,
    GroupDataInline,
)
from .admin_mixins import ChangeSetAwareAdminMixin
from .models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    ClusterTag,
    CustomDataField,
    CustomDataFieldValidatorAssignment,
    Group,
    GroupData,
    Tag,
    Validator,
    ValidatorAssignment,
)

if TYPE_CHECKING:
    from django.http import HttpRequest


class ParamStoreAdmin(usites.UnfoldAdminSite):
    site_header = "Parameter Store"
    site_title = "Parameter Store"
    index_title = "Parameter Store"


param_admin_site = ParamStoreAdmin("param_admin")


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(ChangeSetAwareAdminMixin, GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [ClusterDataInline, ClusterTagInline, ClusterFleetLabelsInline, ClusterIntentInline]
    list_display = ["name", "group", "comma_separated_tags", "changeset_status"]
    list_filter = ["group", "tags__name"]
    search_fields = ["name", "group__name", "tags__name"]
    sortable_by = ["name", "group"]
    ordering = ["group", "name"]
    readonly_fields = (
        "created_at",
        "updated_at",
        "changeset_id",
        "locked_by_changeset",
        "obsoleted_by_changeset",
        "draft_of",
    )
    autocomplete_fields = ("group",)

    @admin.display(description="Cluster Tags")
    def comma_separated_tags(self, obj: "Cluster") -> str:
        """Displays a cluster's tags as a comma-separated string.

        This method is used in the 'list_display' of the ClusterAdmin to provide
        a human-readable list of tags for each cluster. It leverages the
        prefetched 'tags' relation for efficiency.

        Args:
            obj: The Cluster instance.

        Returns:
            A string of comma-separated tag names, or an empty string if there
            are no tags.
        """
        # Now tags are prefetched, so this is efficient
        if hasattr(obj, "prefetched_tags"):  # Check if prefetch is available, for testing
            tags = obj.prefetched_tags
        else:
            tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)
        return ""

    def get_search_results(self, request, queryset, search_term):
        """Filters search results to respect changeset isolation.

        This method extends the default search functionality to filter the results
        based on the active changeset. It ensures that both the admin search and
        any autocomplete fields pointing to this model will only return entities
        that are either live or are drafts within the user's active changeset.

        Args:
            request: The HttpRequest object.
            queryset: The initial queryset to be filtered.
            search_term: The search term entered by the user.

        Returns:
            A tuple containing the filtered queryset and a boolean indicating
            if distinct results should be used.
        """
        from django.db import models

        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        active_changeset_id = request.session.get("active_changeset_id")
        queryset = queryset.filter(
            models.Q(is_live=True)
            | models.Q(changeset_id=active_changeset_id, is_live=False, changeset_id__isnull=False)
        )
        return queryset, use_distinct

    def get_queryset(self, request: "HttpRequest"):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "group", "intent", "changeset_id", "locked_by_changeset", "obsoleted_by_changeset", "draft_of"
            )
            .prefetch_related("tags")
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filters foreign key fields to respect changeset isolation.

        This method ensures that any dropdown or selector for a foreign key
        that points to a changeset-aware model is filtered by the active
        changeset. This prevents a user from selecting a draft entity from an
        inactive changeset.

        Args:
            db_field: The database field for which the form field is being created.
            request: The HttpRequest object.
            **kwargs: Additional keyword arguments for the form field.

        Returns:
            The form field with a correctly filtered queryset.
        """
        from django.db import models

        from .models import ChangeSetAwareTopLevelEntity

        active_changeset_id = request.session.get("active_changeset_id")

        if issubclass(db_field.related_model, ChangeSetAwareTopLevelEntity):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                models.Q(is_live=True)
                | models.Q(changeset_id=active_changeset_id, is_live=False, changeset_id__isnull=False)
            )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Filters many-to-many fields to respect changeset isolation.

        This method ensures that any widget for a many-to-many relationship
        that points to a changeset-aware model is filtered by the active
        changeset. This prevents a user from selecting draft entities from an
        inactive changeset (e.g., for the 'secondary_groups' field).

        Args:
            db_field: The database field for which the form field is being created.
            request: The HttpRequest object.
            **kwargs: Additional keyword arguments for the form field.

        Returns:
            The form field with a correctly filtered queryset.
        """
        from django.db import models

        from .models import ChangeSetAwareTopLevelEntity

        active_changeset_id = request.session.get("active_changeset_id")

        if issubclass(db_field.related_model, ChangeSetAwareTopLevelEntity):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                models.Q(is_live=True)
                | models.Q(changeset_id=active_changeset_id, is_live=False, changeset_id__isnull=False)
            )
        elif db_field.name == "tags":
            kwargs["queryset"] = Tag.objects.all()

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def _copy_child_relations(
        self, original_instance: "Cluster", draft_instance: "Cluster", changeset: "ChangeSet"
    ) -> None:
        """Handles the deep copying of child relationships for a new draft instance.
        This is a required override when using the `ChangeSetAwareAdminMixin`.

        This method is responsible for creating draft copies of all child objects
        (e.g., custom data, fleet labels, intent) that are related to the original
        live cluster. Each new child object is associated with the new draft cluster
        and the active changeset.

        Args:
            original_instance: The live cluster instance from which to copy children.
            draft_instance: The new draft cluster to which the copied children will be linked.
            changeset: The active changeset for the new draft records.
        """
        # Iterate over all custom data related to the original cluster.
        for cluster_data in original_instance.cluster_data.all():
            # Setting pk and id to None ensures that a new object will be created.
            cluster_data.pk = None
            cluster_data.id = None
            # Link the new child object to the draft cluster.
            cluster_data.cluster = draft_instance
            # Mark the new child object as a draft.
            cluster_data.is_live = False
            # Associate the new child object with the active changeset.
            cluster_data.changeset_id = changeset
            cluster_data.save()

        # Iterate over all fleet labels related to the original cluster.
        for fleet_label in original_instance.fleet_labels.all():
            # Setting pk and id to None ensures that a new object will be created.
            fleet_label.pk = None
            fleet_label.id = None
            # Link the new child object to the draft cluster.
            fleet_label.cluster = draft_instance
            # Mark the new child object as a draft.
            fleet_label.is_live = False
            # Associate the new child object with the active changeset.
            fleet_label.changeset_id = changeset
            fleet_label.save()

        # Check if the original cluster has an intent and copy it.
        if hasattr(original_instance, "intent"):
            intent = original_instance.intent
            # Setting pk and id to None ensures that a new object will be created.
            intent.pk = None
            intent.id = None
            # Link the new child object to the draft cluster.
            intent.cluster = draft_instance
            # Mark the new child object as a draft.
            intent.is_live = False
            # Associate the new child object with the active changeset.
            intent.changeset_id = changeset
            intent.save()


@admin.register(Group, site=param_admin_site)
class GroupAdmin(ChangeSetAwareAdminMixin, GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [GroupDataInline]
    list_display = ["name", "changeset_status"]
    sortable_by = ["name"]
    ordering = ["name"]
    readonly_fields = (
        "created_at",
        "updated_at",
        "changeset_id",
        "locked_by_changeset",
        "obsoleted_by_changeset",
        "draft_of",
    )
    search_fields = ("name",)

    def get_search_results(self, request, queryset, search_term):
        """Filters search results to respect changeset isolation.

        This method extends the default search functionality to filter the results
        based on the active changeset. It ensures that both the admin search and
        any autocomplete fields pointing to this model will only return entities
        that are either live or are drafts within the user's active changeset.

        Args:
            request: The HttpRequest object.
            queryset: The initial queryset to be filtered.
            search_term: The search term entered by the user.

        Returns:
            A tuple containing the filtered queryset and a boolean indicating
            if distinct results should be used.
        """
        from django.db import models

        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        active_changeset_id = request.session.get("active_changeset_id")
        queryset = queryset.filter(
            models.Q(is_live=True)
            | models.Q(changeset_id=active_changeset_id, is_live=False, changeset_id__isnull=False)
        )
        return queryset, use_distinct

    def _copy_child_relations(
        self, original_instance: "Group", draft_instance: "Group", changeset: "ChangeSet"
    ) -> None:
        """Handles the deep copying of child relationships for a new draft instance.
        This is a required override when using the `ChangeSetAwareAdminMixin`.

        This method is responsible for creating draft copies of all child objects
        (e.g., custom data) that are related to the original live group. Each new
        child object is associated with the new draft group and the active changeset.

        Args:
            original_instance: The live group instance from which to copy children.
            draft_instance: The new draft group to which the copied children will be linked.
            changeset: The active changeset for the new draft records.
        """
        # Iterate over all custom data related to the original group.
        for group_data in original_instance.group_data.all():
            # Setting pk and id to None ensures that a new object will be created.
            group_data.pk = None
            group_data.id = None
            # Link the new child object to the draft group.
            group_data.group = draft_instance
            # Mark the new child object as a draft.
            group_data.is_live = False
            # Associate the new child object with the active changeset.
            group_data.changeset_id = changeset.id
            group_data.save()


@admin.register(Tag, site=param_admin_site)
class TagAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["name"]
    sortable_by = ["name"]
    ordering = ["name"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClusterTag, site=param_admin_site)
class ClusterTagAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(ClusterFleetLabel, site=param_admin_site)
class ClusterFleetLabelAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["cluster", "key", "value"]
    sortable_by = ["cluster", "key", "value"]
    ordering = ["cluster", "key"]
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(ClusterIntent, site=param_admin_site)
class ClusterIntentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["cluster", "zone_name", "zone_name", "location"]
    list_filter = ["cluster"]
    ordering = ["cluster"]
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(CustomDataField, site=param_admin_site)
class ClusterDataFieldAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClusterData, site=param_admin_site)
class ClusterDataAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster", "field")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(GroupData, site=param_admin_site)
class GroupDataAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "field")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(Validator, site=param_admin_site)
class ValidatorAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["name", "validator"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ValidatorAssignment, site=param_admin_site)
class ValidatorAssignmentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["model_field", "validator"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomDataFieldValidatorAssignment, site=param_admin_site)
class ClusterDataFieldValidatorAssignmentAdmin(uadmin.ModelAdmin):
    list_display = ["field", "validator"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ChangeSet, site=param_admin_site)
class ChangeSetAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    actions = ["commit_changeset", "discard_changeset", "coalesce_changesets"]
    list_display = ["name", "status", "created_by", "created_at"]
    list_filter = ["status", "created_by"]
    search_fields = ["name", "created_by__username"]
    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
        "committed_at",
        "committed_by",
    )

    def get_queryset(self, request):
        """Optimizes the queryset by pre-fetching related user objects."""
        return super().get_queryset(request).select_related("created_by", "committed_by")

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def commit_changeset(self, request, queryset):
        """Commits the selected changesets.

        This action commits the selected changesets, making the changes live. Only changesets in the DRAFT state can be
        committed.

        Args:
            request: The HttpRequest object.
            queryset: The queryset of selected ChangeSet objects.
        """
        from django.db import transaction
        from django.utils import timezone

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        top_level_models = [Group, Cluster]
        child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

        with transaction.atomic():
            for changeset in queryset:
                if changeset.status != ChangeSet.Status.DRAFT:
                    self.message_user(request, f"Changeset '{changeset}' is not in draft state.", level="warning")
                    continue

                # Process top-level entities
                for model in top_level_models:
                    draft_entities = model.objects.filter(changeset_id=changeset.id, is_live=False)
                    for draft_entity in draft_entities:
                        live_entity = (
                            model.objects.filter(shared_entity_id=draft_entity.shared_entity_id, is_live=True).first()
                            if draft_entity.shared_entity_id
                            else None
                        )

                        if draft_entity.is_pending_deletion:
                            if live_entity:
                                live_entity.delete()  # Delete the original live entity
                            draft_entity.delete()  # Delete the deletion draft
                            continue

                        if live_entity:
                            # Demote the old live entity to historical.
                            live_entity.is_locked = False
                            live_entity.locked_by_changeset = None
                            live_entity.is_live = False
                            live_entity.obsoleted_by_changeset = changeset
                            live_entity.save()

                            # Promote the draft entity to live.
                            draft_entity.is_live = True
                            draft_entity.changeset_id = None
                            draft_entity.is_locked = False
                            draft_entity.locked_by_changeset = None
                            draft_entity.draft_of = None
                            draft_entity.save()

                            # Cascade updates for relationships pointing to the old live entity.
                            if model == Group:
                                # Update primary group FK on Clusters.
                                Cluster.objects.filter(group=live_entity).update(group=draft_entity)
                                # Update secondary group M2M on Clusters.
                                clusters_with_secondary = Cluster.objects.filter(secondary_groups=live_entity)
                                for cluster in clusters_with_secondary:
                                    cluster.secondary_groups.remove(live_entity)
                                    cluster.secondary_groups.add(draft_entity)
                        else:
                            # This is a new entity, just promote it to live.
                            draft_entity.is_live = True
                            draft_entity.changeset_id = None
                            draft_entity.is_locked = False
                            draft_entity.locked_by_changeset = None
                            draft_entity.draft_of = None
                            draft_entity.save()

                # Process child entities
                for model in child_models:
                    draft_entities = model.objects.filter(changeset_id=changeset.id, is_live=False)
                    for draft_entity in draft_entities:
                        # Child entities don't have shared_entity_id, they are linked to the parent
                        # The logic to find the old live entity is more complex and depends on the parent.
                        # For now, we just activate the draft entities.
                        draft_entity.is_live = True
                        draft_entity.changeset_id = None
                        draft_entity.save()

                changeset.status = ChangeSet.Status.COMMITTED
                changeset.committed_at = timezone.now()
                changeset.committed_by = request.user
                changeset.save()
                self.message_user(request, f"Changeset '{changeset}' has been committed.")

    commit_changeset.short_description = "Commit selected changesets"

    def discard_changeset(self, request, queryset):
        """Discards the selected changesets.

        This action discards the selected changesets, deleting all associated draft data. Only changesets in the DRAFT
        state can be discarded.

        Args:
            request: The HttpRequest object.
            queryset: The queryset of selected ChangeSet objects.
        """
        from django.db import transaction

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        top_level_models = [Group, Cluster]
        child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

        with transaction.atomic():
            for changeset in queryset:
                if changeset.status != ChangeSet.Status.DRAFT:
                    self.message_user(request, f"Changeset '{changeset}' is not in draft state.", level="warning")
                    continue

                # Unlock parent live entities
                for model in top_level_models:
                    # Find live entities locked by this changeset
                    locked_live_entities = model.objects.filter(locked_by_changeset=changeset, is_live=True)
                    for entity in locked_live_entities:
                        entity.is_locked = False
                        entity.locked_by_changeset = None
                        entity.save()

                # Delete draft rows
                for model in top_level_models:
                    model.objects.filter(changeset_id=changeset.id, is_live=False).delete()

                for model in child_models:
                    model.objects.filter(changeset_id=changeset.id, is_live=False).delete()

                changeset.delete()
                self.message_user(request, f"Changeset '{changeset}' has been discarded.")

    discard_changeset.short_description = "Discard selected changesets"

    def coalesce_changesets(self, request, queryset):
        """Coalesces multiple changesets into a single one.

        This action merges multiple changesets into a single target changeset. The target changeset is the first one
        selected. All other selected changesets will be merged into the target changeset and then deleted.

        Args:
            request: The HttpRequest object.
            queryset: The queryset of selected ChangeSet objects.
        """
        from django.db import transaction

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        if queryset.count() < 2:
            self.message_user(request, "Please select at least two changesets to coalesce.", level="warning")
            return

        with transaction.atomic():
            target_changeset = queryset.first()
            source_changesets = queryset.exclude(pk=target_changeset.pk)

            top_level_models = [Group, Cluster]
            child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

            for changeset in source_changesets:
                if changeset.status != ChangeSet.Status.DRAFT:
                    self.message_user(request, f"Changeset '{changeset}' is not in draft state.", level="warning")
                    continue

                # Re-point the locks on live entities from the source to the target changeset.
                for model in top_level_models:
                    model.objects.filter(locked_by_changeset=changeset).update(locked_by_changeset=target_changeset)

                # Move draft entities from the source to the target changeset.
                for model in top_level_models:
                    model.objects.filter(changeset_id=changeset.id).update(changeset_id=target_changeset.id)

                for model in child_models:
                    model.objects.filter(changeset_id=changeset.id).update(changeset_id=target_changeset.id)

                changeset.delete()

            self.message_user(request, f"Coalesced changesets into '{target_changeset}'.")

    coalesce_changesets.short_description = "Coalesce selected changesets"


@admin.register(User, site=param_admin_site)
class UserAdmin(BaseUserAdmin, uadmin.ModelAdmin):
    pass


@admin.register(AuthGroupModel, site=param_admin_site)
class AuthGroupAdmin(BaseGroupAdmin, uadmin.ModelAdmin):
    pass
