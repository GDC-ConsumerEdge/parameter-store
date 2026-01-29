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
Tests for the Parameter Store History API.

This module contains functional tests verifying the retrieval of historical
versions for Clusters and Groups via the API.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, Cluster, Group

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """
    Helper to create a user and grant them a specific API permission.

    Args:
        permission_to_grant: The full permission codename (e.g. 'api.read_group').

    Returns:
        User: The created user instance with permissions granted.
    """
    user, _ = User.objects.get_or_create(username="testuser", defaults={"password": "password"})
    if not user.check_password("password"):
        user.set_password("password")
        user.save()

    user.user_permissions.clear()

    # Get the ContentType for our custom API permissions
    api_content_type, _ = ContentType.objects.get_or_create(app_label="api", model="customapipermissions")

    # Strip 'api.' prefix for lookup, as codename is stored without it
    codename = permission_to_grant.split(".")[-1]

    perm, _ = Permission.objects.get_or_create(
        codename=codename, content_type=api_content_type, defaults={"name": f"Can {codename}"}
    )
    user.user_permissions.add(perm)
    user.refresh_from_db()
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_group", "api.params_api_read_objects"],
)
def test_group_history(permission_to_grant):
    """
    Test retrieving history for a Group.

    Verifies that multiple commits produce a correct historical trail accessible
    via both name and Entity ID endpoints.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    # 1. Create Initial Live Group (V1)
    ChangeSet.objects.create(name="v1-changeset", created_by=user, status=ChangeSet.Status.COMMITTED)
    group = Group.objects.create(name="history-group", description="V1", is_live=True)

    # 2. Update via ChangeSet A (V1 -> History, Draft -> V2 Live)
    cs_a = ChangeSet.objects.create(name="changeset-A", created_by=user, status=ChangeSet.Status.DRAFT)

    # Create draft
    draft_v2 = group.create_draft(cs_a)
    draft_v2.description = "V2"
    draft_v2.save()

    # Commit ChangeSet A
    cs_a.commit(user)

    # Refresh group to point to V2 (Live)
    group_v2 = Group.objects.get(shared_entity_id=group.shared_entity_id, is_live=True)
    assert group_v2.description == "V2"

    # 3. Update via ChangeSet B (V2 -> History, Draft -> V3 Live)
    cs_b = ChangeSet.objects.create(name="changeset-B", created_by=user, status=ChangeSet.Status.DRAFT)

    # Create draft
    draft_v3 = group_v2.create_draft(cs_b)
    draft_v3.description = "V3"
    draft_v3.save()

    # Commit ChangeSet B
    cs_b.commit(user)

    # Refresh group to point to V3 (Live)
    group_v3 = Group.objects.get(shared_entity_id=group.shared_entity_id, is_live=True)
    assert group_v3.description == "V3"

    # 4. Query History by Name
    response = client.get("/api/v1/group/history-group/history")
    assert response.status_code == 200, f"Failed: {response.content}"
    data = response.json()

    assert data["count"] == 2
    history = data["history"]

    # Most recent history first (V2)
    assert history[0]["entity"]["description"] == "V2"
    assert history[0]["metadata"]["obsoleted_by_changeset_name"] == "changeset-B"

    # Older history (V1)
    assert history[1]["entity"]["description"] == "V1"
    assert history[1]["metadata"]["obsoleted_by_changeset_name"] == "changeset-A"

    # 5. Query History by ID
    response = client.get(f"/api/v1/group/id/{group_v3.shared_entity_id}/history")
    assert response.status_code == 200
    assert response.json()["count"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_cluster_history(permission_to_grant):
    """
    Test retrieving history for a Cluster.

    Verifies that multiple commits produce a correct historical trail accessible
    via both name and Entity ID endpoints.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    group = Group.objects.create(name="cluster-history-group", is_live=True)

    # 1. Create Initial Live Cluster (V1)
    cluster = Cluster.objects.create(name="history-cluster", description="V1", group=group, is_live=True)

    # 2. Update via ChangeSet A
    cs_a = ChangeSet.objects.create(name="cs-A", created_by=user, status=ChangeSet.Status.DRAFT)
    draft_v2 = cluster.create_draft(cs_a)
    draft_v2.description = "V2"
    draft_v2.save()
    cs_a.commit(user)

    cluster_v2 = Cluster.objects.get(shared_entity_id=cluster.shared_entity_id, is_live=True)

    # 3. Update via ChangeSet B
    cs_b = ChangeSet.objects.create(name="cs-B", created_by=user, status=ChangeSet.Status.DRAFT)
    draft_v3 = cluster_v2.create_draft(cs_b)
    draft_v3.description = "V3"
    draft_v3.save()
    cs_b.commit(user)

    cluster_v3 = Cluster.objects.get(shared_entity_id=cluster.shared_entity_id, is_live=True)

    # 4. Query History by Name
    response = client.get("/api/v1/cluster/history-cluster/history")
    assert response.status_code == 200, f"Failed: {response.content}"
    data = response.json()

    assert data["count"] == 2
    history = data["history"]

    assert history[0]["entity"]["description"] == "V2"
    assert history[0]["metadata"]["obsoleted_by_changeset_name"] == "cs-B"

    assert history[1]["entity"]["description"] == "V1"
    assert history[1]["metadata"]["obsoleted_by_changeset_name"] == "cs-A"

    # 5. Query History by ID
    response = client.get(f"/api/v1/cluster/id/{cluster_v3.shared_entity_id}/history")
    assert response.status_code == 200
    assert response.json()["count"] == 2
