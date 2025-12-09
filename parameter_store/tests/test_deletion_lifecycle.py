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
import pytest
from django.contrib.auth.models import User

from parameter_store.models import ChangeSet, Cluster, ClusterTag, Group, Tag

# Mark all tests in this file as requiring database access
pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Creates and returns a superuser."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def changeset(user: User) -> ChangeSet:
    """Creates and returns a draft changeset."""
    return ChangeSet.objects.create(name="Test Changeset", created_by=user)


def test_commit_deletion_draft_retires_live_entity(user, changeset):
    """
    Tests that committing a changeset with a deletion draft retires the live entity
    instead of deleting it from the database.
    """
    # 1. Create a live group
    live_group = Group.objects.create(name="Group to Delete", is_live=True)
    live_group_id = live_group.id

    # 2. Stage for deletion (create draft with is_pending_deletion=True)
    live_group.is_locked = True
    live_group.locked_by_changeset = changeset
    live_group.save()

    Group.objects.create(
        name="Group to Delete",
        is_live=False,
        changeset_id=changeset,
        draft_of=live_group,
        shared_entity_id=live_group.shared_entity_id,
        is_pending_deletion=True,
    )

    # 3. Commit the changeset
    changeset.commit(user)

    # 4. Verify results
    # The group should still exist in the DB
    retired_group = Group.objects.get(id=live_group_id)

    assert retired_group.is_live is False
    assert retired_group.obsoleted_by_changeset == changeset
    assert retired_group.is_locked is False
    assert retired_group.locked_by_changeset is None

    # Verify no drafts remain for this group in the changeset
    assert not Group.objects.filter(changeset_id=changeset.id, shared_entity_id=live_group.shared_entity_id).exists()


def test_commit_cluster_deletion_with_tags(user, changeset):
    """
    Tests that committing a deletion of a Cluster with Tags works correctly.
    This verifies that the manual deletion of child objects in commit() handles
    on_delete=DO_NOTHING constraints (like ClusterTag -> Cluster).
    """
    # 1. Create live data
    live_group = Group.objects.create(name="Parent Group", is_live=True)
    live_cluster = Cluster.objects.create(name="Cluster with Tags", group=live_group, is_live=True)
    tag = Tag.objects.create(name="test-tag")

    # Create a live tag association
    ClusterTag.objects.create(cluster=live_cluster, tag=tag, is_live=True)

    # 2. Stage Cluster for deletion
    live_cluster.is_locked = True
    live_cluster.locked_by_changeset = changeset
    live_cluster.save()

    draft_cluster = Cluster.objects.create(
        name="Cluster with Tags",
        group=live_group,  # FK to live group is fine for this test
        is_live=False,
        changeset_id=changeset,
        draft_of=live_cluster,
        shared_entity_id=live_cluster.shared_entity_id,
        is_pending_deletion=True,
    )

    # IMPORTANT: The draft cluster also has draft tags associated with it (simulating deep copy)
    # This is what caused the FK violation: trying to delete draft_cluster while draft_tag exists.
    ClusterTag.objects.create(cluster=draft_cluster, tag=tag, is_live=False, changeset_id=changeset)

    # 3. Commit
    changeset.commit(user)

    # 4. Verify
    live_cluster.refresh_from_db()
    assert live_cluster.is_live is False

    # Verify draft cluster is gone
    assert not Cluster.objects.filter(id=draft_cluster.id).exists()

    # Verify draft tags are gone
    assert not ClusterTag.objects.filter(changeset_id=changeset.id).exists()
