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
Tests for the Parameter Store Cluster API.

This module contains functional tests verifying CRUD operations, versioning,
and ChangeSet integration for Clusters.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, Cluster, ClusterData, CustomDataField, Group, Tag

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """
    Helper to create a user and grant them a specific API permission.

    Args:
        permission_to_grant: The full permission codename.

    Returns:
        User: The user instance.
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
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_cluster_by_name(permission_to_grant):
    """
    Test retrieving a Cluster by its name.
    """
    user = setup_user_with_permission(permission_to_grant)
    group = Group.objects.create(name="test-group", is_live=True)
    Cluster.objects.create(name="test-cluster", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/cluster/test-cluster")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-cluster"
    assert data["group"] == "test-group"
    assert "id" in data
    assert "record_id" in data
    assert str(data["id"]) != str(data["record_id"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_cluster_by_id(permission_to_grant):
    """
    Test retrieving a Cluster by its stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    group = Group.objects.create(name="test-group", is_live=True)
    c = Cluster.objects.create(name="test-cluster-id", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/cluster/id/{c.shared_entity_id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-cluster-id"
    assert data["record_id"] == c.id
    assert str(data["id"]) == str(c.shared_entity_id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_clusters_list(permission_to_grant):
    """
    Test retrieving a list of Clusters.
    """
    user = setup_user_with_permission(permission_to_grant)
    group = Group.objects.create(name="test-group", is_live=True)
    Cluster.objects.create(name="cluster1", group=group, is_live=True)
    Cluster.objects.create(name="cluster2", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/clusters")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["count"] == 2
    names = [c["name"] for c in data["clusters"]]
    assert "cluster1" in names
    assert "cluster2" in names


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_cluster", "api.params_api_create_objects"],
)
def test_create_cluster_no_changeset(permission_to_grant):
    """
    Test that creating a Cluster without a changeset ID fails with 422.
    """
    user = setup_user_with_permission(permission_to_grant)
    # Use shorter unique name
    suffix = permission_to_grant.split(".")[-1][:10]
    Group.objects.create(name=f"grp-cr-no-cs-{suffix}", is_live=True)
    client = Client()
    client.force_login(user)

    payload = {"name": "no-cs-cluster", "group": f"grp-cr-no-cs-{suffix}", "description": "Should fail"}
    response = client.post("/api/v1/cluster", data=payload, content_type="application/json")
    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_cluster", "api.params_api_update_objects"],
)
def test_update_cluster_no_changeset(permission_to_grant):
    """
    Test that updating a Cluster without a changeset ID fails with 422.
    """
    user = setup_user_with_permission(permission_to_grant)
    # Use shorter unique names
    suffix = permission_to_grant.split(".")[-1][:10]
    group = Group.objects.create(name=f"grp-up-no-cs-{suffix}", is_live=True)
    Cluster.objects.create(name="live-cluster", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated"}
    response = client.put("/api/v1/cluster/live-cluster", data=payload, content_type="application/json")
    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_cluster", "api.params_api_create_objects"],
)
def test_create_cluster_with_changeset(permission_to_grant):
    """
    Test creating a new Cluster draft linked to a ChangeSet.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="test-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="test-group", is_live=True)

    payload = {
        "name": "draft-cluster",
        "description": "In a changeset",
        "group": "test-group",
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/cluster", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cluster = Cluster.objects.get(name="draft-cluster")
    assert cluster.changeset_id == cs


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_cluster", "api.params_api_update_objects"],
)
def test_update_cluster(permission_to_grant):
    """
    Test updating an existing Cluster.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    Cluster.objects.create(name="update-cluster", description="Original", group=group, is_live=False, changeset_id=cs)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated description", "changeset_id": cs.id}
    response = client.put("/api/v1/cluster/update-cluster", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cluster = Cluster.objects.get(name="update-cluster")
    assert cluster.description == "Updated description"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_cluster", "api.params_api_update_objects"],
)
def test_update_cluster_by_id(permission_to_grant):
    """
    Test updating an existing Cluster by stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    c = Cluster.objects.create(name="update-cluster-id", description="Original", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated description via ID", "changeset_id": cs.id}
    response = client.put(f"/api/v1/cluster/id/{c.shared_entity_id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    draft = Cluster.objects.get(draft_of=c, changeset_id=cs)
    assert draft.description == "Updated description via ID"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_cluster", "api.params_api_delete_objects"],
)
def test_delete_cluster_api(permission_to_grant):
    """
    Test staging a Cluster for deletion via DELETE by name.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="delete-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    cluster = Cluster.objects.create(name="cluster-to-delete", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/cluster/cluster-to-delete?changeset_id={cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cluster.refresh_from_db()
    assert cluster.is_locked is True
    assert cluster.locked_by_changeset == cs

    draft = Cluster.objects.get(changeset_id=cs, draft_of=cluster)
    assert draft.is_pending_deletion is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_cluster", "api.params_api_delete_objects"],
)
def test_delete_cluster_by_id_api(permission_to_grant):
    """
    Test staging a Cluster for deletion via stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="delete-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    cluster = Cluster.objects.create(name="cluster-to-delete-id", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/cluster/id/{cluster.shared_entity_id}?changeset_id={cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cluster.refresh_from_db()
    assert cluster.is_locked is True
    assert cluster.locked_by_changeset == cs

    draft = Cluster.objects.get(changeset_id=cs, draft_of=cluster)
    assert draft.is_pending_deletion is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_cluster", "api.params_api_create_objects"],
)
def test_create_cluster_with_relations_and_data(permission_to_grant):
    """Test creating a Cluster draft with secondary groups, tags, fleet labels, data, and intent."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="create-cls-rel-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="primary-group", is_live=True)
    Group.objects.create(name="secondary-group", is_live=True)
    Tag.objects.create(name="edge-tag")
    CustomDataField.objects.create(name="manifest_version")
    CustomDataField.objects.create(name="config_folder")
    CustomDataField.objects.create(name="support_contact")

    payload = {
        "name": "edge-cluster-01",
        "description": "Edge cluster 01",
        "group": "primary-group",
        "secondary_groups": ["secondary-group"],
        "tags": ["edge-tag"],
        "fleet_labels": {"environment": "dev"},
        "data": {
            "manifest_version": "v1.0.0",
            "config_folder": "configs/region-a",
            "support_contact": "ops-team@example.com",
        },
        "intent": {
            "unique_zone_id": "site-00001",
            "location": "us-central1",
            "machine_project_id": "example-machine-proj",
            "fleet_project_id": "example-fleet-proj",
            "secrets_project_id": "example-secrets-proj",
            "node_count": 3,
            "cluster_ipv4_cidr": "172.16.0.0/17",
            "services_ipv4_cidr": "192.168.30.0/23",
            "external_load_balancer_ipv4_address_pools": "10.10.10.244/30",
            "sync_repo": "https://github.com/example/repo.git",
            "sync_branch": "main",
            "sync_dir": "hydrated/clusters/",
            "git_token_secrets_manager_name": "git-token",
            "cluster_version": "1.11.0",
            "subnet_vlans": "410",
            "recreate_on_delete": False,
        },
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/cluster", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    resp_data = response.json()
    assert resp_data["name"] == "edge-cluster-01"
    assert resp_data["secondary_groups"] == ["secondary-group"]
    assert resp_data["tags"] == ["edge-tag"]
    assert resp_data["fleet_labels"] == [{"key": "environment", "value": "dev"}]
    assert resp_data["data"] == {
        "manifest_version": "v1.0.0",
        "config_folder": "configs/region-a",
        "support_contact": "ops-team@example.com",
    }
    assert resp_data["intent"]["unique_zone_id"] == "site-00001"

    cs.commit(user)
    live_cluster = Cluster.objects.with_related().get(name="edge-cluster-01", is_live=True)
    assert [t.name for t in live_cluster.tags.all()] == ["edge-tag"]
    assert {d.field.name: d.value for d in live_cluster.cluster_data.filter(is_live=True)} == {
        "manifest_version": "v1.0.0",
        "config_folder": "configs/region-a",
        "support_contact": "ops-team@example.com",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_cluster", "api.params_api_create_objects"],
)
def test_create_cluster_missing_tag_or_data_field(permission_to_grant):
    """Test creating a Cluster with an unregistered tag or data field returns 404."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="create-cls-404-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="test-group", is_live=True)

    bad_tag_payload = {
        "name": "bad-tag-cluster",
        "group": "test-group",
        "tags": ["missing-tag"],
        "changeset_id": cs.id,
    }
    resp_tag = client.post("/api/v1/cluster", data=bad_tag_payload, content_type="application/json")
    assert resp_tag.status_code == 404
    assert resp_tag.json()["message"] == "Tag 'missing-tag' not found."
    assert not Cluster.objects.filter(name="bad-tag-cluster").exists()

    bad_df_payload = {
        "name": "bad-df-cluster",
        "group": "test-group",
        "data": {"missing_field": "v1"},
        "changeset_id": cs.id,
    }
    resp_df = client.post("/api/v1/cluster", data=bad_df_payload, content_type="application/json")
    assert resp_df.status_code == 404
    assert resp_df.json()["message"] == "Data field 'missing_field' not found."
    assert not Cluster.objects.filter(name="bad-df-cluster").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_cluster", "api.params_api_update_objects"],
)
def test_update_cluster_with_relations_and_data(permission_to_grant):
    """Test updating a live Cluster's data, tags, secondary groups, and fleet labels."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    group = Group.objects.create(name="primary-group", is_live=True)
    sec_group = Group.objects.create(name="secondary-group", is_live=True)
    Tag.objects.create(name="updated-tag")
    field_ver = CustomDataField.objects.create(name="manifest_version")
    CustomDataField.objects.create(name="config_folder")

    live_cluster = Cluster.objects.create(name="edge-cluster-02", group=group, is_live=True)
    ClusterData.objects.create(cluster=live_cluster, field=field_ver, value="v1.0.0", is_live=True)

    cs = ChangeSet.objects.create(name="upd-cls-rel-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {
        "description": "Updated edge cluster",
        "secondary_groups": [sec_group.name],
        "tags": ["updated-tag"],
        "fleet_labels": [{"key": "env", "value": "dev"}],
        "data": {
            "manifest_version": "v2.0.0",
            "config_folder": "configs/region-b",
        },
        "changeset_id": cs.id,
    }
    response = client.put("/api/v1/cluster/edge-cluster-02", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    resp_data = response.json()
    assert resp_data["description"] == "Updated edge cluster"
    assert resp_data["secondary_groups"] == ["secondary-group"]
    assert resp_data["tags"] == ["updated-tag"]
    assert resp_data["fleet_labels"] == [{"key": "env", "value": "dev"}]
    assert resp_data["data"] == {
        "manifest_version": "v2.0.0",
        "config_folder": "configs/region-b",
    }

    cs.commit(user)
    promoted = Cluster.objects.with_related().get(name="edge-cluster-02", is_live=True)
    assert {d.field.name: d.value for d in promoted.cluster_data.filter(is_live=True)} == {
        "manifest_version": "v2.0.0",
        "config_folder": "configs/region-b",
    }
