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
Tests for the Parameter Store Group API.

This module contains functional tests verifying CRUD operations, versioning,
and ChangeSet integration for Groups.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, CustomDataField, Group, GroupData

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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_with_data(permission_to_grant):
    """Test creating a new Group draft with custom data fields."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="create-grp-data-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    CustomDataField.objects.create(name="manifest_version")
    CustomDataField.objects.create(name="config_folder")

    payload = {
        "name": "data-group",
        "description": "Group with data",
        "data": {
            "manifest_version": "v1.0.0",
            "config_folder": "configs/region-a",
        },
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/group", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    resp_data = response.json()
    assert resp_data["name"] == "data-group"
    assert resp_data["data"] == {
        "manifest_version": "v1.0.0",
        "config_folder": "configs/region-a",
    }

    cs.commit(user)
    live_group = Group.objects.get(name="data-group", is_live=True)
    assert {d.field.name: d.value for d in live_group.group_data.filter(is_live=True)} == {
        "manifest_version": "v1.0.0",
        "config_folder": "configs/region-a",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_with_unknown_data_field(permission_to_grant):
    """Test creating a Group with an unregistered data field returns 404."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="create-grp-bad-df-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {
        "name": "bad-data-group",
        "data": {"non_existent_field": "val"},
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/group", data=payload, content_type="application/json")
    assert response.status_code == 404
    assert response.json()["message"] == "Data field 'non_existent_field' not found."
    assert not Group.objects.filter(name="bad-data-group").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group_with_data(permission_to_grant):
    """Test updating a Group's custom data fields and committing the ChangeSet."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    field_ver = CustomDataField.objects.create(name="manifest_version")
    CustomDataField.objects.create(name="support_contact")

    live_group = Group.objects.create(name="upd-data-group", description="Initial", is_live=True)
    GroupData.objects.create(group=live_group, field=field_ver, value="v1.0.0", is_live=True)

    cs = ChangeSet.objects.create(name="upd-grp-data-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {
        "description": "Updated with data",
        "data": {
            "manifest_version": "v2.0.0",
            "support_contact": "ops-team@example.com",
        },
        "changeset_id": cs.id,
    }
    response = client.put("/api/v1/group/upd-data-group", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    resp_data = response.json()
    assert resp_data["description"] == "Updated with data"
    assert resp_data["data"] == {
        "manifest_version": "v2.0.0",
        "support_contact": "ops-team@example.com",
    }

    cs.commit(user)
    promoted_group = Group.objects.get(name="upd-data-group", is_live=True)
    assert {d.field.name: d.value for d in promoted_group.group_data.filter(is_live=True)} == {
        "manifest_version": "v2.0.0",
        "support_contact": "ops-team@example.com",
    }


@pytest.mark.django_db
def test_update_group_data_null_and_empty_removal() -> None:
    """Tests key-level removal via null and full collection removal via empty dict on Group data."""
    user = setup_user_with_permission("api.params_api_update_group")
    client = Client()
    client.force_login(user)

    field_a = CustomDataField.objects.create(name="field_a")
    field_b = CustomDataField.objects.create(name="field_b")
    CustomDataField.objects.create(name="field_c")

    live_group = Group.objects.create(name="semantics-group", is_live=True)
    GroupData.objects.create(group=live_group, field=field_a, value="val_a", is_live=True)
    GroupData.objects.create(group=live_group, field=field_b, value="val_b", is_live=True)

    cs = ChangeSet.objects.create(name="semantics-grp-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    # 1. Update field_a, omit field_b (untouched), remove field_b in next step, add field_c
    resp1 = client.put(
        "/api/v1/group/semantics-group",
        data={
            "data": {"field_a": "val_a_v2", "field_c": "val_c"},
            "changeset_id": cs.id,
        },
        content_type="application/json",
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"] == {
        "field_a": "val_a_v2",
        "field_b": "val_b",
        "field_c": "val_c",
    }

    # 2. Explicitly remove field_b by setting it to None; omit field_a and field_c
    resp2 = client.put(
        "/api/v1/group/semantics-group",
        data={
            "data": {"field_b": None},
            "changeset_id": cs.id,
        },
        content_type="application/json",
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"] == {
        "field_a": "val_a_v2",
        "field_c": "val_c",
    }

    # 3. Clear all custom data by passing an empty dict {}
    resp3 = client.put(
        "/api/v1/group/semantics-group",
        data={
            "data": {},
            "changeset_id": cs.id,
        },
        content_type="application/json",
    )
    assert resp3.status_code == 200
    assert resp3.json()["data"] is None

    cs.commit(user)
    promoted = Group.objects.get(name="semantics-group", is_live=True)
    assert not promoted.group_data.filter(is_live=True).exists()


@pytest.mark.django_db
def test_group_custom_data_validator_error_keyed_by_field_name() -> None:
    """Tests that custom data validation errors on Group return 422 keyed by the custom field name."""
    from parameter_store.models import CustomDataFieldValidatorAssignment, Validator

    user = setup_user_with_permission("api.params_api_create_group")
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="val-grp-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    env_field = CustomDataField.objects.create(name="environment")
    enum_val = Validator.objects.create(
        name="env-enum",
        validator="parameter_store.validation.EnumValidator",
        parameters={"choices": ["dev", "prod"]},
    )
    CustomDataFieldValidatorAssignment.objects.create(field=env_field, validator=enum_val)

    resp = client.post(
        "/api/v1/group",
        data={
            "name": "invalid-data-group",
            "data": {"environment": "invalid-env"},
            "changeset_id": cs.id,
        },
        content_type="application/json",
    )
    assert resp.status_code == 422
    msg = resp.json()["message"]
    assert "environment" in msg
    assert "field" not in msg


@pytest.mark.django_db
def test_update_group_staged_for_deletion_returns_409() -> None:
    """Tests that updating a group already staged for deletion in the same ChangeSet returns 409 Conflict."""
    user = User.objects.create_superuser("del_upd_grp_admin", "del_upd_grp@example.com", "password")
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="del-upd-grp-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    live_group = Group.objects.create(name="doomed-update-group", description="Original", is_live=True)

    del_resp = client.delete(f"/api/v1/group/doomed-update-group?changeset_id={cs.id}")
    assert del_resp.status_code == 200

    # Attempt update by name in the same ChangeSet
    upd_by_name = client.put(
        "/api/v1/group/doomed-update-group",
        data={"description": "Should fail", "changeset_id": cs.id},
        content_type="application/json",
    )
    assert upd_by_name.status_code == 409
    assert "staged for deletion" in upd_by_name.json()["message"]

    # Attempt update by shared_entity_id in the same ChangeSet
    upd_by_id = client.put(
        f"/api/v1/group/id/{live_group.shared_entity_id}",
        data={"description": "Should also fail", "changeset_id": cs.id},
        content_type="application/json",
    )
    assert upd_by_id.status_code == 409
    assert "staged for deletion" in upd_by_id.json()["message"]
