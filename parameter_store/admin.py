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
import unfold.admin as uadmin
import unfold.sites as usites
from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .admin_inlines import (
    ClusterDataInline,
    ClusterFleetLabelsInline,
    ClusterIntentInline,
    ClusterTagInline,
    GroupDataInline,
)
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


class ParamStoreAdmin(usites.UnfoldAdminSite):
    site_header = "Edge Parameter Store"
    site_title = "Edge Parameter Store"
    index_title = "Edge Parameter Store"

    def get_app_list(self, request, app_label=None):
        """Return a sorted list of all the installed apps that have been registered to this
        site.
        """
        ordering = {
            "ChangeSets": 1,
            "Clusters": 2,
            "Groups": 3,
            "Tags": 4,
            "Cluster Intent": 5,
            "Cluster Fleet Labels": 6,
            "Cluster Custom Data Fields": 7,
            "Cluster Custom Data": 8,
            "Validators": 9,
            "Standard Data Validator Assignments": 10,
            "Cluster Custom Data Validator Assignments": 11,
        }
        app_dict = self._build_app_dict(request, app_label)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())

        # Sort the models alphabetically within each app.
        for app in app_list:
            app["models"].sort(key=lambda x: ordering.get(x["name"], 1000))

        return app_list


param_admin_site = ParamStoreAdmin("param_admin")


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [ClusterDataInline, ClusterTagInline, ClusterFleetLabelsInline, ClusterIntentInline]
    list_display = ["name", "group", "comma_separated_tags"]
    list_filter = ["group", "tags__name"]
    search_fields = ["name", "group__name", "tags__name"]
    sortable_by = ["name", "group"]
    ordering = ["group", "name"]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Cluster Tags")
    def comma_separated_tags(self, obj):
        # Now tags are prefetched, so this is efficient
        if hasattr(obj, "prefetched_tags"):  # Check if prefetch is available, for testing
            tags = obj.prefetched_tags
        else:
            tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)
        return ""

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "intent").prefetch_related("tags")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            kwargs["queryset"] = Tag.objects.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Group, site=param_admin_site)
class GroupAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [GroupDataInline]
    list_display = ["name"]
    sortable_by = ["name"]
    ordering = ["name"]
    readonly_fields = ("created_at", "updated_at")


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
                        live_entity = model.objects.filter(
                            shared_entity_id=draft_entity.shared_entity_id, is_live=True
                        ).first()
                        if live_entity:
                            live_entity.is_live = False
                            live_entity.save()

                        draft_entity.is_live = True
                        draft_entity.changeset_id = None
                        draft_entity.is_locked = False
                        # When is_locked is false, the changeset_id should be null.
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

                # Unlock top-level entities
                for model in top_level_models:
                    locked_entities = model.objects.filter(changeset_id=changeset.id, is_locked=True)
                    for entity in locked_entities:
                        entity.is_locked = False
                        entity.changeset_id = None
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

                for model in top_level_models:
                    model.objects.filter(changeset_id=changeset.id).update(changeset_id=target_changeset.id)

                for model in child_models:
                    model.objects.filter(changeset_id=changeset.id).update(changeset_id=target_changeset.id)

                changeset.delete()

            self.message_user(request, f"Coalesced changesets into '{target_changeset}'.")

    coalesce_changesets.short_description = "Coalesce selected changesets"
