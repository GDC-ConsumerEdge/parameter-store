###############################################################################
# Copyright 2026 Google, LLC
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
Tests for database constraints and utility helpers.

This module adds coverage for newly introduced conditional unique constraints
and the `capture_db_errors` context manager that converts database integrity
errors into Django `ValidationError`s with field-aware messages.
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    CustomDataField,
    Group,
)
from parameter_store.util import capture_db_errors

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Provides a superuser for ChangeSet creation in tests."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def changeset(user: User) -> ChangeSet:
    """Creates a draft ChangeSet owned by the provided user."""
    return ChangeSet.objects.create(name="CS", created_by=user)


def test_capture_db_errors_maps_unique_constraint_fields_for_group() -> None:
    """Ensures duplicate live group name raises field-specific ValidationError via capture_db_errors.

    This verifies that the context manager parses the database error and maps it
    back to the `name` field based on the `unique_live_group_name` constraint.
    """
    Group.objects.create(name="Retail-East", is_live=True)

    with pytest.raises(ValidationError) as excinfo:
        with capture_db_errors(model_class=Group):
            Group.objects.create(name="Retail-East", is_live=True)

    assert isinstance(excinfo.value, ValidationError)
    assert hasattr(excinfo.value, "message_dict")
    # The unique constraint targets the "name" field.
    assert "name" in excinfo.value.message_dict
    assert any("unique constraint" in msg for msg in excinfo.value.message_dict["name"])


def test_unique_draft_cluster_field_enforced_and_mapped(changeset: ChangeSet) -> None:
    """Two draft ClusterData rows with the same field in one ChangeSet must be rejected.

    Validates the `unique_draft_cluster_field` constraint by attempting to create
    a duplicate draft row and asserting that `capture_db_errors` raises a
    `ValidationError` mapping messages to the relevant fields.
    """
    # Create a draft Cluster and a reusable custom field.
    live_group = Group.objects.create(name="G1", is_live=True)
    draft_cluster = Cluster.objects.create(name="C1", group=live_group, is_live=False, changeset_id=changeset)
    field = CustomDataField.objects.create(name="env")

    # First draft value is allowed.
    ClusterData.objects.create(cluster=draft_cluster, field=field, value="prod", is_live=False, changeset_id=changeset)

    # Duplicate draft value for the same (cluster, field, changeset) should violate the constraint.
    with pytest.raises(ValidationError) as excinfo:
        with capture_db_errors(model_class=ClusterData):
            ClusterData.objects.create(
                cluster=draft_cluster, field=field, value="prod", is_live=False, changeset_id=changeset
            )

    assert isinstance(excinfo.value, ValidationError)
    assert hasattr(excinfo.value, "message_dict")
    msg_dict = excinfo.value.message_dict
    # All constrained fields should appear; at least assert the most user-meaningful ones.
    assert "field" in msg_dict
    assert any("unique constraint" in msg for msg in msg_dict["field"])


def test_unique_draft_cluster_key_enforced_and_mapped(changeset: ChangeSet) -> None:
    """Duplicate draft ClusterFleetLabel keys in one ChangeSet must be rejected.

    Validates the `unique_draft_cluster_key` constraint, asserting that the
    resulting `ValidationError` is mapped to the constrained fields.
    """
    live_group = Group.objects.create(name="G2", is_live=True)
    draft_cluster = Cluster.objects.create(name="C2", group=live_group, is_live=False, changeset_id=changeset)

    # First draft label is allowed.
    ClusterFleetLabel.objects.create(
        cluster=draft_cluster, key="tier", value="gold", is_live=False, changeset_id=changeset
    )

    # Duplicate key for the same cluster within the same ChangeSet should violate the constraint.
    with pytest.raises(ValidationError) as excinfo:
        with capture_db_errors(model_class=ClusterFleetLabel):
            ClusterFleetLabel.objects.create(
                cluster=draft_cluster, key="tier", value="gold", is_live=False, changeset_id=changeset
            )

    assert isinstance(excinfo.value, ValidationError)
    assert hasattr(excinfo.value, "message_dict")
    msg_dict = excinfo.value.message_dict
    assert "key" in msg_dict
    assert any("unique constraint" in msg for msg in msg_dict["key"])
