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

from parameter_store.models import ChangeSet, Cluster, Group

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


@pytest.fixture
def live_group() -> Group:
    """Creates and returns a live test group."""
    return Group.objects.create(name="Live Group", is_live=True)


@pytest.fixture
def draft_group(live_group: Group, changeset: ChangeSet) -> Group:
    """Creates a draft from the live group and locks the live group."""
    live_group.is_locked = True
    live_group.locked_by_changeset = changeset
    live_group.save()
    return Group.objects.create(
        name="Live Group",  # Same name to simulate the real scenario
        is_live=False,
        changeset_id=changeset,
        draft_of=live_group,
        shared_entity_id=live_group.shared_entity_id,
    )


@pytest.fixture
def live_cluster(live_group: Group) -> Cluster:
    """Creates and returns a live test cluster."""
    return Cluster.objects.create(name="Live Cluster", group=live_group, is_live=True)


@pytest.fixture
def draft_cluster(live_cluster: Cluster, changeset: ChangeSet) -> Cluster:
    """Creates a draft from the live cluster and locks the live cluster."""
    live_cluster.is_locked = True
    live_cluster.locked_by_changeset = changeset
    live_cluster.save()
    return Cluster.objects.create(
        name="Live Cluster",
        group=live_cluster.group,
        is_live=False,
        changeset_id=changeset,
        draft_of=live_cluster,
        shared_entity_id=live_cluster.shared_entity_id,
    )


def test_delete_draft_group_unlocks_parent(live_group: Group, draft_group: Group):
    """
    Verify that when a draft Group is deleted individually (using the .delete()
    method), the post_delete signal handler correctly unlocks the parent live Group.
    """
    live_group.refresh_from_db()
    assert live_group.is_locked is True
    assert live_group.locked_by_changeset is not None

    draft_group.delete()

    live_group.refresh_from_db()
    assert live_group.is_locked is False
    assert live_group.locked_by_changeset is None


def test_delete_draft_cluster_unlocks_parent(live_cluster: Cluster, draft_cluster: Cluster):
    """
    Verify that when a draft Cluster is deleted individually (using the .delete()
    method), the post_delete signal handler correctly unlocks the parent live Cluster.
    """
    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is True
    assert live_cluster.locked_by_changeset is not None

    draft_cluster.delete()

    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is False
    assert live_cluster.locked_by_changeset is None


def test_bulk_delete_draft_group_unlocks_parent(live_group: Group, draft_group: Group):
    """
    Verify that when a draft Group is deleted as part of a bulk operation
    (using queryset.delete()), the post_delete signal handler correctly unlocks
    the parent live Group.
    """
    live_group.refresh_from_db()
    assert live_group.is_locked is True

    Group.objects.filter(pk=draft_group.pk).delete()

    live_group.refresh_from_db()
    assert live_group.is_locked is False
    assert live_group.locked_by_changeset is None
