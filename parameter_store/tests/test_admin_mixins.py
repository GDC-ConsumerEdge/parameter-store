###############################################################################
# Copyright 2024 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may- not use this file except in compliance with the License.
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

from parameter_store.admin import ClusterAdmin
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


def test_create_draft_action(cluster_admin: ClusterAdmin, cluster: Cluster, user: User, rf: RequestFactory):
    """
    Verify that the 'Create Draft & Edit' admin action successfully creates a
    new draft from a live Cluster, correctly locks the original live entity,
    and associates the new draft with a changeset.
    """
    request = rf.get("/")
    request.user = user
    request.session = {}  # Using an in-memory session for the test
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)

    queryset = Cluster.objects.filter(pk=cluster.pk)

    cluster_admin.create_draft_action(request, queryset)

    assert Cluster.objects.count() == 2

    # Refresh the original cluster from the DB to check that it became locked.
    cluster.refresh_from_db()
    assert cluster.is_locked is True

    # Verify the new draft was created with the correct properties.
    draft_cluster = Cluster.objects.get(is_live=False)
    assert draft_cluster.changeset_id is not None
    assert draft_cluster.changeset_id.created_by == user
    assert draft_cluster.name == cluster.name


def test_response_change_on_live_entity_creates_draft(
    cluster_admin: ClusterAdmin, cluster: Cluster, user: User, rf: RequestFactory
):
    """
    Verify that saving a live entity via the admin change form does not
    modify the entity directly, but instead creates a new draft and redirects
    to the draft's change page.
    """
    request = rf.post(f"/admin/parameter_store/cluster/{cluster.pk}/change", data={"name": "Updated Name"})
    request.user = user
    request.session = {}
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)

    response = cluster_admin.response_change(request, cluster)

    # Check that a new draft was created.
    assert Cluster.objects.count() == 2
    draft_cluster = Cluster.objects.get(is_live=False)
    assert draft_cluster is not None

    # Check that the original cluster is now locked.
    cluster.refresh_from_db()
    assert cluster.is_locked is True
    assert cluster.locked_by_changeset is not None

    # Check that the new draft has the correct properties.
    assert draft_cluster.draft_of == cluster
    assert draft_cluster.changeset_id == cluster.locked_by_changeset
    assert draft_cluster.changeset_id.created_by == user

    # Check that the response is a redirect to the new draft's admin page.
    assert response.status_code == 302
    assert response.url == f"/params/parameter_store/cluster/{draft_cluster.pk}/change/"
