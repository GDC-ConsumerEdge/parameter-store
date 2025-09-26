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
    models.UniqueConstraint(
        fields=["shared_entity_id"],
        condition=models.Q(is_live=False),
        name="unique_draft_%(class)s",
    ),
    # A draft record must always point to the live record it was drafted from.
    models.CheckConstraint(
        condition=~models.Q(is_live=False) | models.Q(draft_of__isnull=False),
        name="draft_must_have_draft_of_%(class)s",
    ),
    # A live record cannot be a draft of another record; its draft_of field must be null.
    models.CheckConstraint(
        condition=~models.Q(is_live=True) | models.Q(draft_of__isnull=True),
        name="live_must_not_have_draft_of_%(class)s",
    ),
    # If a live record is locked, it must be associated with the changeset that holds its draft.
    models.CheckConstraint(
        condition=~models.Q(is_locked=True) | models.Q(locked_by_changeset__isnull=False),
        name="locked_must_have_locked_by_changeset_%(class)s",
    ),
    # An unlocked record cannot have a locking changeset.
    models.CheckConstraint(
        condition=~models.Q(is_locked=False) | models.Q(locked_by_changeset__isnull=True),
        name="unlocked_must_not_have_locked_by_changeset_%(class)s",
    ),
    # A draft record must always belong to a changeset.
    models.CheckConstraint(
        condition=~models.Q(is_live=False) | models.Q(changeset_id__isnull=False),
        name="draft_must_have_changeset_id_%(class)s",
    ),
    # A live record, representing the stable state, is not part of any changeset.
    models.CheckConstraint(
        condition=~models.Q(is_live=True) | models.Q(changeset_id__isnull=True),
        name="live_must_not_have_changeset_id_%(class)s",
    ),
]
