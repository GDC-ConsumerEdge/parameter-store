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
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from parameter_store.admin import ChangeSetAdmin
from parameter_store.models import ChangeSet, Cluster, Group

# Mark all tests in this file as requiring database access
pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Creates and returns a superuser."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def rf() -> RequestFactory:
    """Returns a RequestFactory instance."""
    return RequestFactory()


@pytest.fixture
def changeset_admin() -> ChangeSetAdmin:
    """Returns an instance of ChangeSetAdmin."""
    site = admin.AdminSite()
    return ChangeSetAdmin(ChangeSet, site)


@pytest.fixture
def setup_commit_data(user):
    """Sets up a complete scenario for testing a changeset commit."""
    changeset = ChangeSet.objects.create(name="Commit Test", created_by=user)
    live_group = Group.objects.create(name="Live Group", is_live=True)
    draft_group = Group.objects.create(
        name="Live Group",
        is_live=False,
        changeset_id=changeset,
        draft_of=live_group,
        shared_entity_id=live_group.shared_entity_id,
    )
    live_group.is_locked = True
    live_group.locked_by_changeset = changeset
    live_group.save()

    live_cluster = Cluster.objects.create(name="Live Cluster", group=live_group, is_live=True)

    return changeset, live_group, draft_group, live_cluster


def test_commit_changeset(changeset_admin, user, rf, setup_commit_data):
    """
    Verify that the 'commit_changeset' admin action correctly promotes a draft
    Group to live, demotes the old live Group to historical, and cascades the
    necessary foreign key updates to related models like Cluster.
    """
    changeset, live_group, draft_group, live_cluster = setup_commit_data
    request = rf.get("/")
    request.user = user
    request.session = {}
    setattr(request, "_messages", FallbackStorage(request))

    changeset_admin.commit_changeset(request, ChangeSet.objects.filter(pk=changeset.pk))

    changeset.refresh_from_db()
    assert changeset.status == ChangeSet.Status.COMMITTED
    assert changeset.committed_by == user

    # Check that the old live group is now historical and the draft is now live.
    live_group.refresh_from_db()
    draft_group.refresh_from_db()
    assert live_group.is_live is False
    assert live_group.obsoleted_by_changeset == changeset
    assert draft_group.is_live is True
    assert draft_group.changeset_id is None

    # Verify that the cluster's foreign key was re-pointed to the new live group.
    live_cluster.refresh_from_db()
    assert live_cluster.group == draft_group


def test_discard_changeset(changeset_admin, user, rf):
    """
    Verify that the 'discard_changeset' admin action successfully deletes the
    changeset, deletes the associated draft Group, and unlocks the original
    live Group.
    """
    changeset = ChangeSet.objects.create(name="Discard Test", created_by=user)
    live_group = Group.objects.create(name="Live Group", is_live=True)
    Group.objects.create(
        name="Live Group",
        is_live=False,
        changeset_id=changeset,
        draft_of=live_group,
        shared_entity_id=live_group.shared_entity_id,
    )
    live_group.is_locked = True
    live_group.locked_by_changeset = changeset
    live_group.save()

    request = rf.get("/")
    request.user = user
    request.session = {}
    setattr(request, "_messages", FallbackStorage(request))

    assert Group.objects.count() == 2
    assert ChangeSet.objects.count() == 1

    changeset_admin.discard_changeset(request, ChangeSet.objects.filter(pk=changeset.pk))

    assert ChangeSet.objects.count() == 0
    assert Group.objects.count() == 1  # Only the live group should remain.
    live_group.refresh_from_db()
    assert live_group.is_locked is False
    assert live_group.locked_by_changeset is None


def test_coalesce_changesets(changeset_admin, user, rf):
    """
    Verify that the 'coalesce_changesets' admin action correctly merges draft
    records from a source changeset into a target changeset, deletes the source,
    and re-points the lock on the live entity to the target changeset.
    """
    target_cs = ChangeSet.objects.create(name="Target", created_by=user)
    source_cs = ChangeSet.objects.create(name="Source", created_by=user)

    live_group = Group.objects.create(name="Live Group", is_live=True)
    draft_group = Group.objects.create(
        name="Live Group",
        is_live=False,
        changeset_id=source_cs,
        draft_of=live_group,
        shared_entity_id=live_group.shared_entity_id,
    )
    live_group.is_locked = True
    live_group.locked_by_changeset = source_cs
    live_group.save()

    request = rf.get("/")
    request.user = user
    request.session = {}
    setattr(request, "_messages", FallbackStorage(request))

    # Coalesce source_cs into target_cs. The target is determined by creation order.
    queryset = ChangeSet.objects.filter(pk__in=[target_cs.pk, source_cs.pk]).order_by("pk")
    changeset_admin.coalesce_changesets(request, queryset)

    # The source changeset should be deleted.
    assert ChangeSet.objects.count() == 1
    assert ChangeSet.objects.first() == target_cs

    # The draft group should now belong to the target changeset.
    draft_group.refresh_from_db()
    assert draft_group.changeset_id == target_cs

    # The live group's lock should be re-pointed to the target changeset.
    live_group.refresh_from_db()
    assert live_group.is_locked is True
    assert live_group.locked_by_changeset == target_cs
