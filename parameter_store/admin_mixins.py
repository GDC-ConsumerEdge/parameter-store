###############################################################################
# Copyright 2024 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (a "License");
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
import logging
from typing import Optional

from django.contrib import admin, messages
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from parameter_store.models import Cluster, Group
from parameter_store.util import get_or_create_changeset

logger = logging.getLogger(__name__)


class ChangeSetAwareAdminMixin:
    """A mixin for ModelAdmin classes of top-level entities that are ChangeSet-aware.

    This mixin provides functionality to create a draft of a live entity, filter the queryset to
    show only live entities or drafts in the active changeset, and restrict direct editing of live
    entities.
    """

    actions = ["create_draft_action"]
    list_display = ["name", "group", "comma_separated_tags", "changeset_status"]

    def get_queryset(self, request):
        """Filters the queryset to show all live and draft entities for the current user."""
        qs = super().get_queryset(request)
        return qs.filter(
            models.Q(is_live=True) | models.Q(changeset_id__created_by=request.user, is_live=False)
        ).select_related("changeset_id", "locked_by_changeset")

    @admin.display(description="Changeset Status")
    def changeset_status(self, obj):
        """Displays the status of the changeset associated with a draft entity.

        Args:
            obj: The model instance.

        Returns:
            A string indicating the changeset status, or "Live" if the entity is live.
        """
        if obj.is_live:
            return "Live"
        if obj.changeset_id:
            active_changeset_id = self.request.session.get("active_changeset_id")
            if obj.changeset_id.id == active_changeset_id:
                return f"Draft in active changeset: {obj.changeset_id.name}"
            return f"Draft in changeset: {obj.changeset_id.name}"
        return "Draft (no changeset)"

    @admin.action(description="Create Draft & Edit")
    def create_draft_action(self, request, queryset) -> Optional[HttpResponseRedirect]:
        """Creates a draft copy of a live entity within a changeset context.

        This Django admin action is intended for a single, live, unlocked entity. It will
        automatically create and activate a new changeset if one is not already active. Upon
        successful creation of the draft, it redirects the user to the draft's change page.

        Args:
            request: The HttpRequest object.
            queryset: The queryset of selected entities.

        Returns:
            An HttpResponseRedirect to the new draft's change page on success, otherwise None.
        """
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one entity to create a draft.", level=messages.WARNING)
            return

        instance = queryset.first()

        if not instance.is_live:
            self.message_user(request, "You can only create a draft from a live entity.", level=messages.WARNING)
            return

        if instance.is_locked:
            self.message_user(
                request, "This entity is locked by another changeset. Cannot create a new draft.", level=messages.ERROR
            )
            return

        changeset = get_or_create_changeset(request)

        try:
            with transaction.atomic():
                draft_instance = self.deep_copy_instance(instance, changeset)
                instance.is_locked = True
                instance.locked_by_changeset = changeset
                instance.save()

                return redirect(
                    reverse(
                        f"param_admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                        args=[draft_instance.pk],
                    )
                )
        except Exception as e:
            logger.exception("Failed to create draft for instance %s", instance.pk)
            self.message_user(request, f"An unexpected error occurred: {e}", level=messages.ERROR)

    def save_model(self, request, obj, form, change):
        """
        Overrides the default save_model to intercept changes to live entities.

        If the object is live, this method prevents the direct update, creates a
        draft copy, applies the form changes to the draft, and locks the live
        object. For entities that are already drafts, it calls the default
        `save_model` method to proceed with the standard save behavior.
        """
        if obj.pk and obj.is_live:
            # This is an existing, live object. Intercept the save.
            changeset = get_or_create_changeset(request)
            original_instance = self.model.objects.get(pk=obj.pk)

            if original_instance.is_locked:
                self.message_user(
                    request,
                    "This entity is locked by another changeset. Cannot create a new draft.",
                    level=messages.ERROR,
                )
                return

            try:
                with transaction.atomic():
                    # 1. Create a draft from the original, unmodified instance.
                    draft_instance = self.deep_copy_instance(original_instance, changeset)

                    # 2. Apply the changes from the form to the new draft instance.
                    m2m_fields = [f.name for f in self.model._meta.many_to_many]
                    for field, value in form.cleaned_data.items():
                        if field in m2m_fields:
                            continue
                        setattr(draft_instance, field, value)
                    draft_instance.save()

                    # Handle Many-to-Many relationships separately.
                    for field in self.model._meta.many_to_many:
                        if field.name in form.cleaned_data:
                            getattr(draft_instance, field.name).set(form.cleaned_data[field.name])

                    # 3. Lock the original live instance.
                    original_instance.is_locked = True
                    original_instance.locked_by_changeset = changeset
                    original_instance.save()

                    # 4. Store the new draft's pk in the request to redirect to it later.
                    request._draft_created_pk = draft_instance.pk
                    self.message_user(
                        request,
                        f"A draft was created for {original_instance.name} and your changes were saved to it.",
                        level=messages.SUCCESS,
                    )
            except Exception as e:
                logger.exception("Failed to create draft for instance %s", original_instance.pk)
                self.message_user(request, f"An unexpected error occurred: {e}", level=messages.ERROR)
        else:
            # This is a new object or an existing draft, save it normally.
            super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        """
        Overrides the default change response to handle redirection to the new draft.
        """
        # If a draft was created in save_model, redirect to its change page.
        if hasattr(request, "_draft_created_pk"):
            return redirect(
                reverse(
                    f"param_admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                    args=[request._draft_created_pk],
                )
            )
        return super().response_change(request, obj)

    def deep_copy_instance(self, original_instance, changeset):
        """Performs a deep copy of a model instance and its related children.

        This method creates a new draft instance from a live one, preserving its data and
        many-to-many relationships. It then invokes `_copy_child_relations` to handle the
        duplication of related child objects.

        Args:
            original_instance: The model instance to copy.
            changeset: The changeset to associate with the new draft.

        Returns:
            The newly created draft instance.
        """
        # Create a new instance in memory
        draft_instance = self.model()

        # Copy attributes from the original instance
        for field in original_instance._meta.fields:
            # Don't copy the primary key
            if field.primary_key:
                continue
            setattr(draft_instance, field.name, getattr(original_instance, field.name))

        # Set the new state for the draft and save to get a PK
        draft_instance.shared_entity_id = original_instance.shared_entity_id
        draft_instance.is_live = False
        draft_instance.is_locked = False
        draft_instance.changeset_id = changeset
        draft_instance.draft_of = original_instance
        draft_instance.save()

        # Now that the draft has a PK, we can set M2M relationships
        for field in original_instance._meta.many_to_many:
            getattr(draft_instance, field.name).set(getattr(original_instance, field.name).all())

        # Copy the child relations from the original to the new draft
        self._copy_child_relations(original_instance, draft_instance, changeset)

        # If the model being copied is a Group, we need to check if there are any
        # draft Clusters in the same changeset that need their group FK updated.
        if isinstance(draft_instance, Group):
            clusters_in_changeset = Cluster.objects.filter(changeset_id=changeset.id, is_live=False)
            for cluster in clusters_in_changeset:
                if cluster.group == original_instance:
                    cluster.group = draft_instance
                    cluster.save()

        return draft_instance

    def _copy_child_relations(self, original_instance, draft_instance, changeset):
        """Handles the deep copying of child relationships for a new draft instance.

        This method must be implemented by the ModelAdmin class that uses this mixin. It is
        responsible for iterating through the child objects of the original instance and
        creating corresponding copies linked to the new draft instance.

        Args:
            original_instance: The original live instance from which children are copied.
            draft_instance: The new draft instance to which copied children will be linked.
            changeset: The active changeset to be associated with the new child drafts.

        Raises:
            NotImplementedError: If the method is not overridden in the consuming ModelAdmin.
        """
        raise NotImplementedError("You must implement _copy_child_relations in your ModelAdmin.")
