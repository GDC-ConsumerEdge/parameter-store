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
"""
Tests for the Parameter Store Group API.

This module contains functional tests verifying CRUD operations, versioning,
and ChangeSet integration for Groups.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, Group

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
    ["api.params_api_read_group", "api.params_api_read_objects"],
)
def test_get_group_by_name(permission_to_grant):
    """
    Test retrieving a Group by its name.
    """
    user = setup_user_with_permission(permission_to_grant)
    Group.objects.create(name="test-group", description="A test group", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/group/test-group")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-group"
    assert data["description"] == "A test group"
    assert "id" in data
    assert "record_id" in data
    assert str(data["id"]) != str(data["record_id"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_group", "api.params_api_read_objects"],
)
def test_get_group_by_id(permission_to_grant):
    """
    Test retrieving a Group by its stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    g = Group.objects.create(name="test-group-id", description="A test group by ID", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/group/id/{g.shared_entity_id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-group-id"
    assert data["description"] == "A test group by ID"
    assert data["record_id"] == g.id
    assert str(data["id"]) == str(g.shared_entity_id)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_group", "api.params_api_read_objects"],
)
def test_get_groups_list(permission_to_grant):
    """
    Test retrieving a list of Groups.
    """
    user = setup_user_with_permission(permission_to_grant)
    Group.objects.create(name="group1", is_live=True)
    Group.objects.create(name="group2", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/groups")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["count"] == 2
    names = [g["name"] for g in data["groups"]]
    assert "group1" in names
    assert "group2" in names


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_no_changeset(permission_to_grant):
    """
    Test that creating a Group without a changeset ID fails with 422.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    payload = {"name": "no-cs-group", "description": "Should fail"}
    response = client.post("/api/v1/group", data=payload, content_type="application/json")
    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group_no_changeset(permission_to_grant):
    """
    Test that updating a Group without a changeset ID fails with 422.
    """
    user = setup_user_with_permission(permission_to_grant)
    # Use shorter unique name
    suffix = permission_to_grant.split(".")[-1][:10]
    Group.objects.create(name=f"lg-no-cs-{suffix}", description="Original", is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated"}
    response = client.put(f"/api/v1/group/lg-no-cs-{suffix}", data=payload, content_type="application/json")
    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_with_changeset(permission_to_grant):
    """
    Test creating a new Group draft linked to a ChangeSet.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="test-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {"name": "draft-group", "description": "In a changeset", "changeset_id": cs.id}
    response = client.post("/api/v1/group", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    group = Group.objects.get(name="draft-group")
    assert group.changeset_id == cs


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group(permission_to_grant):
    """
    Test updating an existing Group.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="update-group", description="Original description", is_live=False, changeset_id=cs)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated description", "changeset_id": cs.id}
    response = client.put("/api/v1/group/update-group", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    group = Group.objects.get(name="update-group")
    assert group.description == "Updated description"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group_by_id(permission_to_grant):
    """
    Test updating an existing Group by stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    g = Group.objects.create(name="update-group-id", description="Original description", is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated description via ID", "changeset_id": cs.id}
    response = client.put(f"/api/v1/group/id/{g.shared_entity_id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    # Check that a draft was created and updated
    draft = Group.objects.get(draft_of=g, changeset_id=cs)
    assert draft.description == "Updated description via ID"
    assert draft.is_live is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_validation_error(permission_to_grant):
    """
    Test creating a new Group with invalid data triggers a validation error.
    """
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="test-validation-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {
        "name": "a-very-very-long-group-name-that-exceeds-thirty-characters",
        "description": "Invalid group",
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/group", data=payload, content_type="application/json")

    assert response.status_code == 422
    data = response.json()
    assert "name" in data["message"]
    assert "ensure this value has at most 30 characters" in str(data["message"]["name"][0]).lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group_validation_error(permission_to_grant):
    """
    Test updating a Group with invalid data triggers a validation error.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-validation-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="valid-name", description="Original", is_live=False, changeset_id=cs)

    client = Client()
    client.force_login(user)

    long_description = "a" * 256
    payload = {"description": long_description, "changeset_id": cs.id}
    response = client.put("/api/v1/group/valid-name", data=payload, content_type="application/json")

    assert response.status_code == 422
    data = response.json()
    assert "description" in data["message"]
    assert "ensure this value has at most 255 characters" in str(data["message"]["description"][0]).lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_group", "api.params_api_delete_objects"],
)
def test_delete_group_api(permission_to_grant):
    """
    Test staging a Group for deletion via name-based DELETE.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="delete-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="group-to-delete", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/group/group-to-delete?changeset_id={cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    group.refresh_from_db()
    assert group.is_locked is True
    assert group.locked_by_changeset == cs

    draft = Group.objects.get(changeset_id=cs, draft_of=group)
    assert draft.is_pending_deletion is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_group", "api.params_api_delete_objects"],
)
def test_delete_group_by_id_api(permission_to_grant):
    """
    Test staging a Group for deletion via stable Entity ID.
    """
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="delete-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="group-to-delete-id", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/group/id/{group.shared_entity_id}?changeset_id={cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    group.refresh_from_db()
    assert group.is_locked is True
    assert group.locked_by_changeset == cs

    draft = Group.objects.get(changeset_id=cs, draft_of=group)
    assert draft.is_pending_deletion is True
