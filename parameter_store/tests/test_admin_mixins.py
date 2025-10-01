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
from django.test import Client
from django.urls import reverse

from parameter_store.admin import ClusterAdmin
from parameter_store.models import ChangeSet, Cluster, Group

# Mark all tests in this file as requiring database access
pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Provides a superuser for authentication in tests."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def client(user) -> Client:
    """Provides a Django test client with a logged-in user."""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def live_objects():
    """Provides a set of live Group and Cluster objects for testing drafts."""
    live_group = Group.objects.create(name="live-group", is_live=True)
    live_cluster = Cluster.objects.create(name="live-cluster", group=live_group, is_live=True)
    return live_group, live_cluster


def test_create_draft_action(client, live_objects, user):
    """
    Tests that the 'Create Draft & Edit' action creates a draft correctly.

    This test verifies that the admin action creates a new draft from a live
    entity, locks the original, and associates the new draft with a changeset.
    """
    _, live_cluster = live_objects
    url = reverse("param_admin:parameter_store_cluster_changelist")
    data = {"action": "create_draft_action", "_selected_action": [live_cluster.pk]}
    response = client.post(url, data)

    assert response.status_code == 302
    assert Cluster.objects.count() == 2

    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is True

    draft_cluster = Cluster.objects.get(is_live=False)
    assert draft_cluster.changeset_id is not None
    assert draft_cluster.changeset_id.created_by == user
    assert draft_cluster.name == live_cluster.name


def run_draft_update_test_logic(changeset, live_group, live_cluster):
    """
    A helper function to run the core logic for draft update tests.

    This function centralizes the assertion logic to ensure that when a draft
    Group is modified, its changes correctly propagate to a draft Cluster
    within the same changeset, while live objects remain untouched.
    """
    original_live_group_name = live_group.name

    draft_cluster = Cluster.objects.get(is_live=False, changeset_id=changeset.id)
    draft_group = Group.objects.get(is_live=False, changeset_id=changeset.id)

    live_group.refresh_from_db()
    live_cluster.refresh_from_db()
    draft_cluster.refresh_from_db()
    draft_group.refresh_from_db()

    assert live_group.name == original_live_group_name, "Live group's name should not change."
    assert live_cluster.group == live_group, "Live cluster's group should not change."
    assert draft_cluster.group == draft_group, "Draft cluster's group should point to the draft group."


def test_draft_update_via_post(client, live_objects, user):
    """
    Tests that updating a group draft correctly updates a cluster draft.

    This test simulates a user creating a draft of a cluster, then editing the
    live group via a POST request, which should trigger the creation of a
    draft group and the update of the draft cluster.
    """
    live_group, live_cluster = live_objects

    # 1. Create a draft of the cluster to start
    session = client.session
    changeset = ChangeSet.objects.create(name="test-changeset", created_by=user)
    session["active_changeset_id"] = changeset.id
    session.save()

    cluster_admin_url = reverse("param_admin:parameter_store_cluster_changelist")
    client.post(cluster_admin_url, {"action": "create_draft_action", "_selected_action": [live_cluster.pk]})

    # 2. Post an update to the live group
    group_admin_url = reverse("param_admin:parameter_store_group_change", args=[live_group.pk])
    post_data = {
        "name": "draft-group-name",
        "description": "Updated description",
        "group_data-TOTAL_FORMS": "0",
        "group_data-INITIAL_FORMS": "0",
    }

    # Ensure the active changeset is in the session for the POST request
    session = client.session
    session["active_changeset_id"] = changeset.id
    session.save()

    client.post(group_admin_url, post_data, follow=True)

    run_draft_update_test_logic(changeset, live_group, live_cluster)


def test_draft_cluster_remains_visible_after_group_update(client, live_objects, user):
    """
    Tests that a draft cluster remains visible after its group is updated.

    This test replicates a bug where a draft cluster would disappear from the
    admin list view after its parent group was modified within the same changeset.
    """
    live_group, live_cluster = live_objects
    site = admin.AdminSite()
    cluster_admin = ClusterAdmin(Cluster, site)

    # 1. Create a draft of the cluster
    session = client.session
    changeset = ChangeSet.objects.create(name="visibility-test-changeset", created_by=user)
    session["active_changeset_id"] = changeset.id
    session.save()

    cluster_admin_url = reverse("param_admin:parameter_store_cluster_changelist")
    client.post(cluster_admin_url, {"action": "create_draft_action", "_selected_action": [live_cluster.pk]})

    # 2. Verify the draft cluster is visible
    request = client.get(cluster_admin_url).wsgi_request
    request.session = client.session
    queryset = cluster_admin.get_queryset(request)
    draft_cluster_pk = Cluster.objects.get(is_live=False).pk
    assert queryset.filter(is_live=False, pk=draft_cluster_pk).exists()

    # 3. Update the group in the same changeset
    group_admin_url = reverse("param_admin:parameter_store_group_change", args=[live_group.pk])
    post_data = {
        "name": "updated-group-name",
        "description": "Updated description",
        "group_data-TOTAL_FORMS": "0",
        "group_data-INITIAL_FORMS": "0",
    }
    client.post(group_admin_url, post_data)

    # 4. Verify the draft cluster is still visible
    request = client.get(cluster_admin_url).wsgi_request
    request.session = client.session
    queryset = cluster_admin.get_queryset(request)
    draft_cluster_pk = Cluster.objects.get(is_live=False).pk  # Re-fetch the pk
    assert queryset.filter(is_live=False, pk=draft_cluster_pk).exists()
