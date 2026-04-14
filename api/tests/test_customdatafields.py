"""Tests for the Custom Data Field API endpoints.

These tests ensure that custom data fields can be correctly created, retrieved, and updated
via the REST API endpoints.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import CustomDataField

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """
    Helper to create a user and grant them a specific API permission.

    Args:
        permission_to_grant: The full permission codename (e.g. 'api.read_customdatafield').

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
    ["api.params_api_read_customdatafield", "api.params_api_read_objects"],
)
def test_get_custom_data_fields(permission_to_grant):
    """Test retrieving a list of custom data fields."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    CustomDataField.objects.create(name="field1", description="First field")
    CustomDataField.objects.create(name="field2", description="Second field")

    response = client.get("/api/v1/custom-data-fields")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 2  # Could be more if other tests created some

    names = [item["name"] for item in data["items"]]
    assert "field1" in names
    assert "field2" in names


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_customdatafield", "api.params_api_create_objects"],
)
def test_create_custom_data_field(permission_to_grant):
    """Test creating a new custom data field."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    payload = {"name": "new-field", "description": "A newly created field"}
    response = client.post("/api/v1/custom-data-fields", data=payload, content_type="application/json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["name"] == "new-field"
    assert data["description"] == "A newly created field"

    assert CustomDataField.objects.filter(name="new-field").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_customdatafield", "api.params_api_create_objects"],
)
def test_create_custom_data_field_duplicate(permission_to_grant):
    """Test creating a custom data field that already exists returns 409."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    CustomDataField.objects.create(name="existing-field", description="Already exists")

    payload = {"name": "existing-field", "description": "Duplicate attempt"}
    response = client.post("/api/v1/custom-data-fields", data=payload, content_type="application/json")

    assert response.status_code == 409
    assert "already exists" in response.json()["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_customdatafield", "api.params_api_update_objects"],
)
def test_update_custom_data_field(permission_to_grant):
    """Test updating an existing custom data field's description."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    field = CustomDataField.objects.create(name="updatable-field", description="Old description")

    payload = {"description": "New description"}
    response = client.put(f"/api/v1/custom-data-fields/{field.name}", data=payload, content_type="application/json")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updatable-field"
    assert data["description"] == "New description"

    field.refresh_from_db()
    assert field.description == "New description"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_customdatafield", "api.params_api_update_objects"],
)
def test_update_custom_data_field_not_found(permission_to_grant):
    """Test updating a non-existent custom data field returns 404."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    payload = {"description": "Should fail"}
    response = client.put(
        "/api/v1/custom-data-fields/non-existent-field", data=payload, content_type="application/json"
    )

    assert response.status_code == 404
    assert "not found" in response.json()["message"]
