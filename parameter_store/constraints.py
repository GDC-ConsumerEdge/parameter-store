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
"""
This module defines a set of reusable database constraints for top-level, changeset-aware models. These constraints
are critical for maintaining the data integrity of the live/draft entity system. They enforce the business logic that
prevents corruption/inconsistency by ensuring that entities adhere to the expected states and relationships within a
changeset context, such as guaranteeing the uniqueness of live and draft entities and maintaining the consistency of
their locks.
"""

from django.db import models

top_level_constraints = [
    # Ensures that for any given shared_entity_id, only one record can be marked as live.
    models.UniqueConstraint(
        fields=["shared_entity_id"],
        condition=models.Q(is_live=True),
        name="unique_live_%(class)s",
    ),
    # Ensures that for any given shared_entity_id, only one record can be a draft.
    # A draft is defined as a record that is not live and is part of a changeset.
    models.UniqueConstraint(
        fields=["shared_entity_id"],
        condition=models.Q(is_live=False, changeset_id__isnull=False),
        name="unique_draft_%(class)s",
    ),
    # Enforces the correct state of the 'draft_of' field based on the record's status (live, draft, or historical).
    models.CheckConstraint(
        condition=(
            # Draft
            models.Q(is_live=True, draft_of__isnull=True)
            # New draft object or draft of existing
            | models.Q(is_live=False, changeset_id__isnull=False)
            # Historical
            | models.Q(is_live=False, obsoleted_by_changeset__isnull=False, draft_of__isnull=True)
        ),
        name="valid_draft_of_state_by_status_%(class)s",
    ),
    # Enforces the correct locking state based on the record's status.
    models.CheckConstraint(
        condition=(
            # A live, locked record must have a locking changeset.
            models.Q(is_live=True, is_locked=True, locked_by_changeset__isnull=False)
            # A live, unlocked record must not have a locking changeset.
            | models.Q(is_live=True, is_locked=False, locked_by_changeset__isnull=True)
            # A non-live record (draft or historical) must never be locked.
            | models.Q(is_live=False, is_locked=False, locked_by_changeset__isnull=True)
        ),
        name="valid_lock_state_by_status_%(class)s",
    ),
    # A non-live record must be exclusively either a draft or historical.
    models.CheckConstraint(
        condition=models.Q(is_live=True)
        | (
            # Is a draft: changeset_id is set AND obsoleted_by_changeset is NOT set
            models.Q(changeset_id__isnull=False, obsoleted_by_changeset__isnull=True)
            # OR is historical: changeset_id is NOT set AND obsoleted_by_changeset is set
            | models.Q(changeset_id__isnull=True, obsoleted_by_changeset__isnull=False)
        ),
        name="non_live_must_be_draft_or_historical_%(class)s",
    ),
    # A live record, representing the stable state, is not part of any changeset.
    models.CheckConstraint(
        condition=~models.Q(is_live=True) | models.Q(changeset_id__isnull=True),
        name="live_must_not_have_changeset_id_%(class)s",
    ),
]
