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

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from parameter_store.models import ChangeSet, Cluster, ClusterData, CustomDataField, Group, GroupData

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
def other_user() -> User:
    """Provides another superuser for testing isolation."""
    return User.objects.create_superuser("other", "other@example.com", "password")


@pytest.fixture
def other_client(other_user) -> Client:
    """Provides another Django test client."""
    client = Client()
    client.force_login(other_user)
    return client


def test_custom_data_changeset_lifecycle_e2e(client, other_client, user, other_user):
    """
    E2E test for custom data (ClusterData/GroupData) within ChangeSets.

    Verifies:
    1. Visible within the active changeset.
    2. Invisible from another changeset.
    3. Commits successfully and becomes live.
    """
    # 0. Setup: Create live Cluster, Group and CustomDataField
    live_group = Group.objects.create(name="Live Group", is_live=True)
    live_cluster = Cluster.objects.create(name="Live Cluster", group=live_group, is_live=True)
    custom_field = CustomDataField.objects.create(name="test_field")

    # 1. Create ChangeSet A and activate it for client
    changeset_a = ChangeSet.objects.create(name="CS A", created_by=user)
    session = client.session
    session["active_changeset_id"] = changeset_a.id
    session.save()

    # 2. Create ChangeSet B and activate it for other_client
    changeset_b = ChangeSet.objects.create(name="CS B", created_by=other_user)
    session = other_client.session
    session["active_changeset_id"] = changeset_b.id
    session.save()

    # 3. Add Custom Data to Cluster in ChangeSet A
    # We'll simulate this by posting to the Cluster's change page for the LIVE cluster,
    # which should trigger draft creation and saving of inlines to the draft.
    cluster_change_url = reverse("param_admin:parameter_store_cluster_change", args=[live_cluster.pk])

    # Form data for Cluster + ClusterData inline
    # We need to know the prefix for ClusterData inline, which is 'cluster_data'
    post_data = {
        "name": "Live Cluster",
        "group": live_group.pk,
        "cluster_data-TOTAL_FORMS": "1",
        "cluster_data-INITIAL_FORMS": "0",
        "cluster_data-MIN_NUM_FORMS": "0",
        "cluster_data-MAX_NUM_FORMS": "1000",
        "cluster_data-0-field": custom_field.pk,
        "cluster_data-0-value": "value-in-a",
        "cluster_data-0-id": "",
        "clustertag_set-TOTAL_FORMS": "0",
        "clustertag_set-INITIAL_FORMS": "0",
        "clustertag_set-MIN_NUM_FORMS": "0",
        "clustertag_set-MAX_NUM_FORMS": "1000",
        "fleet_labels-TOTAL_FORMS": "0",
        "fleet_labels-INITIAL_FORMS": "0",
        "fleet_labels-MIN_NUM_FORMS": "0",
        "fleet_labels-MAX_NUM_FORMS": "1000",
        "intent-TOTAL_FORMS": "0",
        "intent-INITIAL_FORMS": "0",
        "intent-MIN_NUM_FORMS": "0",
        "intent-MAX_NUM_FORMS": "1",
        "_save": "Save",
    }

    response = client.post(cluster_change_url, post_data, follow=True)
    if response.status_code != 200 or Cluster.objects.count() != 2:
        print(response.content.decode())
    assert response.status_code == 200

    # Verify draft was created and ClusterData was saved to it
    assert Cluster.objects.count() == 2
    draft_cluster = Cluster.objects.get(is_live=False, changeset_id=changeset_a)
    assert ClusterData.objects.count() == 1
    cd = ClusterData.objects.get(cluster=draft_cluster)
    assert cd.value == "value-in-a"
    assert cd.is_live is False
    assert cd.changeset_id == changeset_a

    # 4. Add Custom Data to Group in ChangeSet A
    group_change_url = reverse("param_admin:parameter_store_group_change", args=[live_group.pk])
    post_data = {
        "name": "Live Group",
        "group_data-TOTAL_FORMS": "1",
        "group_data-INITIAL_FORMS": "0",
        "group_data-MIN_NUM_FORMS": "0",
        "group_data-MAX_NUM_FORMS": "1000",
        "group_data-0-field": custom_field.pk,
        "group_data-0-value": "group-value-in-a",
        "group_data-0-id": "",
        "_save": "Save",
    }
    response = client.post(group_change_url, post_data, follow=True)
    assert response.status_code == 200

    assert Group.objects.count() == 2
    draft_group = Group.objects.get(is_live=False, changeset_id=changeset_a)
    assert GroupData.objects.count() == 1
    gd = GroupData.objects.get(group=draft_group)
    assert gd.value == "group-value-in-a"
    assert gd.is_live is False
    assert gd.changeset_id == changeset_a

    # 5. Verify visibility within ChangeSet A
    # The draft cluster change page should show the custom data
    draft_cluster_change_url = reverse("param_admin:parameter_store_cluster_change", args=[draft_cluster.pk])
    response = client.get(draft_cluster_change_url)
    assert b"value-in-a" in response.content

    draft_group_change_url = reverse("param_admin:parameter_store_group_change", args=[draft_group.pk])
    response = client.get(draft_group_change_url)
    assert b"group-value-in-a" in response.content

    # 6. Verify invisibility from ChangeSet B
    # other_client (in CS B) should not see the draft data when viewing the live cluster/group
    # Note: they can't even see the drafts in the changelist if we filtered properly,
    # but let's check the live object's view.
    response = other_client.get(cluster_change_url)
    assert b"value-in-a" not in response.content

    response = other_client.get(group_change_url)
    assert b"group-value-in-a" not in response.content

    # 7. Commit ChangeSet A
    # We can call the admin action or call commit() directly.
    # The user asked to "hijack the E2E (to verify it commits) test" if possible.
    # Let's use the admin action to be truly E2E.
    changeset_changelist_url = reverse("param_admin:parameter_store_changeset_changelist")
    data = {
        "action": "commit_changeset",
        "_selected_action": [changeset_a.pk],
    }
    response = client.post(changeset_changelist_url, data, follow=True)
    assert response.status_code == 200

    changeset_a.refresh_from_db()
    assert changeset_a.status == ChangeSet.Status.COMMITTED

    # 8. Verify live state
    # The draft cluster should now be live, and its data should be live and associated with it.
    draft_cluster.refresh_from_db()
    assert draft_cluster.is_live is True
    assert draft_cluster.changeset_id is None

    cd.refresh_from_db()
    assert cd.is_live is True
    assert cd.changeset_id is None
    assert cd.cluster == draft_cluster

    draft_group.refresh_from_db()
    assert draft_group.is_live is True
    assert draft_group.changeset_id is None

    gd.refresh_from_db()
    assert gd.is_live is True
    assert gd.changeset_id is None
    assert gd.group == draft_group

    # Verify visibility in live admin pages (now without any active changeset)
    session = client.session
    session.pop("active_changeset_id", None)
    session.save()

    cluster_live_url = reverse("param_admin:parameter_store_cluster_change", args=[draft_cluster.pk])
    response = client.get(cluster_live_url)
    assert b"value-in-a" in response.content

    group_live_url = reverse("param_admin:parameter_store_group_change", args=[draft_group.pk])
    response = client.get(group_live_url)
    assert b"group-value-in-a" in response.content
