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

from parameter_store.admin import ClusterAdmin, GroupAdmin
from parameter_store.models import Cluster, Group

# Mark all tests in this file as requiring database access
pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Creates and returns a superuser."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def group() -> Group:
    """Creates and returns a test group."""
    return Group.objects.create(name="Test Group", is_live=True)


@pytest.fixture
def cluster(group: Group) -> Cluster:
    """Creates and returns a test cluster associated with the group fixture."""
    return Cluster.objects.create(name="Test Cluster", group=group, is_live=True)


@pytest.fixture
def rf() -> RequestFactory:
    """Returns a RequestFactory instance."""
    return RequestFactory()


@pytest.fixture
def cluster_admin() -> ClusterAdmin:
    """Returns an instance of ClusterAdmin."""
    site = admin.AdminSite()
    return ClusterAdmin(Cluster, site)


@pytest.fixture
def group_admin() -> GroupAdmin:
    """Returns an instance of GroupAdmin."""
    site = admin.AdminSite()
    return GroupAdmin(Group, site)


def test_response_change_on_live_cluster_creates_draft(
    cluster_admin: ClusterAdmin, cluster: Cluster, user: User, rf: RequestFactory
):
    """
    Verify that attempting to save a live Cluster via the admin change form
    intercepts the request, creates a new draft of the cluster, and redirects
    the user to the new draft's admin page.
    """
    request = rf.post(f"/admin/parameter_store/cluster/{cluster.pk}/change/", data={"name": "Updated Name"})
    request.user = user
    request.session = {}
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)

    response = cluster_admin.response_change(request, cluster)

    # Check that a new draft was created and the original is now locked.
    assert Cluster.objects.count() == 2
    draft_cluster = Cluster.objects.get(is_live=False)
    assert draft_cluster is not None

    cluster.refresh_from_db()
    assert cluster.is_locked is True
    assert cluster.locked_by_changeset is not None

    # Verify the new draft is correctly linked to the original and the changeset.
    assert draft_cluster.draft_of == cluster
    assert draft_cluster.changeset_id == cluster.locked_by_changeset
    assert draft_cluster.changeset_id.created_by == user

    # Ensure the user is redirected to the new draft's change page.
    assert response.status_code == 302
    assert response.url == f"/params/parameter_store/cluster/{draft_cluster.pk}/change/"


def test_response_change_on_live_group_creates_draft(
    group_admin: GroupAdmin, group: Group, user: User, rf: RequestFactory
):
    """
    Verify that attempting to save a live Group via the admin change form
    intercepts the request, creates a new draft of the group, and redirects
    the user to the new draft's admin page.
    """
    request = rf.post(f"/admin/parameter_store/group/{group.pk}/change/", data={"name": "Updated Name"})
    request.user = user
    request.session = {}
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)

    response = group_admin.response_change(request, group)

    # Check that a new draft was created and the original is now locked.
    assert Group.objects.count() == 2
    draft_group = Group.objects.get(is_live=False)
    assert draft_group is not None

    group.refresh_from_db()
    assert group.is_locked is True
    assert group.locked_by_changeset is not None

    # Verify the new draft is correctly linked to the original and the changeset.
    assert draft_group.draft_of == group
    assert draft_group.changeset_id == group.locked_by_changeset
    assert draft_group.changeset_id.created_by == user

    # Ensure the user is redirected to the new draft's change page.
    assert response.status_code == 302
    assert response.url == f"/params/parameter_store/group/{draft_group.pk}/change/"
