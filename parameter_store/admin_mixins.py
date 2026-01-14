###############################################################################
# Copyright 2026 Google, LLC
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

import unfold.admin as uadmin
from django.contrib import admin, messages
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from parameter_store.util import get_or_create_changeset

logger = logging.getLogger(__name__)


class ChangeSetAwareAdminMixin(uadmin.ModelAdmin):
    """A mixin for ModelAdmin classes of top-level entities that are ChangeSet-aware.

    This mixin provides functionality to create a draft of a live entity, filter the queryset to
    show only live entities or drafts in the active changeset, and restrict direct editing of live
    entities.
    """

    actions = ["create_draft_action", "stage_for_deletion_action"]
    list_display = ["name", "group", "comma_separated_tags", "changeset_status"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if object_id:
            try:
                obj = self.get_object(request, object_id)
                if obj and obj.is_pending_deletion:
                    self.message_user(
                        request,
                        "WARNING: This entity is marked for DELETION in the active ChangeSet. "
                        "Committing the ChangeSet will retire this record.",
                        level=messages.WARNING,
                    )
            except Exception:
                pass
        return super().change_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        """Filters the queryset to show all live and draft entities for the current user."""
        qs = super().get_queryset(request)
        return qs.filter(
            models.Q(is_live=True) | models.Q(changeset_id__created_by=request.user, is_live=False)
        ).select_related("changeset_id", "locked_by_changeset")

    @admin.display(description="ChangeSet Status")
    def changeset_status(self, obj):
        """Displays the status of the changeset associated with a draft entity.

        Args:
            obj: The model instance.

        Returns:
            A string indicating the changeset status, or "Live" if the entity is live.
        """
        from django.utils.safestring import mark_safe

        if obj.is_live:
            return "Live"

        status_text = ""
        # Default blue: Light mode (bg-blue-100 text-blue-800), Dark mode (bg-blue-500/20 dark:text-blue-200)
        badge_color = "bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-200"

        if obj.changeset_id:
            active_changeset_id = self.request.session.get("active_changeset_id")
            if obj.changeset_id.id == active_changeset_id:
                status_text = f"Draft in active ChangeSet: {obj.changeset_id.name}"
            else:
                status_text = f"Draft in ChangeSet: {obj.changeset_id.name}"
        else:
            status_text = "Draft (no ChangeSet)"

        if getattr(obj, "is_pending_deletion", False):
            status_text += " (Pending Deletion)"
            # Red: Light mode (bg-red-100 text-red-800), Dark mode (bg-red-500/20 dark:text-red-200)
            badge_color = "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200"

        # Using Tailwind classes for the badge, consistent with Unfold
        return mark_safe(
            f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {badge_color}">{status_text}</span>'
        )

    # The `stage_for_deletion_action` is for bulk actions on the list view.
    # The `delete_model` and `delete_view` methods handle single object deletions.

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
                request, "This entity is locked by another ChangeSet. Cannot create a new draft.", level=messages.ERROR
            )
            return

        changeset = get_or_create_changeset(request, create_if_none=True)

        try:
            with transaction.atomic():
                draft_instance = instance.create_draft(changeset)
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
        Overrides the default save_model to handle changeset-aware entities.

        - For new objects, it creates them as drafts within a changeset.
        - For existing live objects, it intercepts the change, creates a draft,
          applies the changes to the draft, and locks the live object.
        - For existing draft objects, it saves the changes normally.
        """
        changeset = get_or_create_changeset(request, create_if_none=True)

        if not change:
            # This is a new object; create it as a draft
            obj.is_live = False
            obj.changeset_id = changeset
            obj.draft_of = None
            obj.is_locked = False
            super().save_model(request, obj, form, change)
        elif obj.is_live:
            # This is an existing, live object. Intercept the save to create a draft.
            original_instance = self.model.objects.get(pk=obj.pk)

            if original_instance.is_locked:
                self.message_user(
                    request,
                    "This entity is locked by another ChangeSet. Cannot create a new draft.",
                    level=messages.ERROR,
                )
                return

            try:
                with transaction.atomic():
                    # Create a draft from the original, unmodified instance.
                    draft_instance = original_instance.create_draft(changeset)

                    # Apply the changes from the form to the new draft instance.
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

                    # Lock the original live instance.
                    original_instance.is_locked = True
                    original_instance.locked_by_changeset = changeset
                    original_instance.save()

                    # Store the new draft's pk in the request to redirect to it later.
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
            # This is an existing draft, save it normally.
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

    @admin.action(description="Delete / Stage for Deletion")
    def stage_for_deletion_action(self, request, queryset):
        """Stages selected live entities for deletion or deletes drafts."""
        changeset = get_or_create_changeset(request, create_if_none=True)

        success_count = 0
        with transaction.atomic():
            for obj in queryset:
                if obj.is_live:
                    if obj.is_locked:
                        self.message_user(request, f"Skipping locked entity: {obj}", level=messages.WARNING)
                        continue

                    # Create deletion draft
                    obj.create_draft(changeset, is_pending_deletion=True)

                    # Lock live entity
                    obj.is_locked = True
                    obj.locked_by_changeset = changeset
                    obj.save()
                    success_count += 1
                else:
                    # It's a draft, just delete it (discard changes)
                    obj.delete()
                    success_count += 1

        if success_count > 0:
            self.message_user(request, f"Successfully processed {success_count} items.", level=messages.SUCCESS)

    def delete_view(self, request, object_id, extra_context=None):
        """
        Overrides the default delete view to handle changeset-aware staging for deletion.
        This prevents the standard 'deleted successfully' message from appearing when
        we only staged the item.
        """
        if request.method == "POST":
            obj = self.get_object(request, object_id)
            if obj and obj.is_live:
                # Bypass standard deletion logic for live objects
                self.delete_model(request, obj)
                # Redirect to the changelist (or wherever successful deletion goes)
                return HttpResponseRedirect(
                    reverse(f"param_admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist")
                )

        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        """
        Overrides the default delete behavior.
        If the object is live, stage it for deletion in the active changeset.
        If the object is a draft, delete it (discard changes).
        """
        changeset = get_or_create_changeset(request, create_if_none=True)

        if obj.is_live:
            if obj.is_locked:
                self.message_user(
                    request,
                    f"Entity {obj} is locked by another ChangeSet. Cannot stage for deletion.",
                    level=messages.ERROR,
                )
                return

            try:
                with transaction.atomic():
                    # Create deletion draft
                    obj.create_draft(changeset, is_pending_deletion=True)

                    # Lock live entity
                    obj.is_locked = True
                    obj.locked_by_changeset = changeset
                    obj.save()

                    self.message_user(
                        request,
                        f"Entity {obj} has been staged for deletion in ChangeSet '{changeset.name}'.",
                        level=messages.SUCCESS,
                    )
            except Exception as e:
                logger.exception("Failed to stage %s for deletion", obj)
                self.message_user(request, f"An unexpected error occurred: {e}", level=messages.ERROR)
        else:
            # It's a draft, just delete it (discard changes)
            super().delete_model(request, obj)
