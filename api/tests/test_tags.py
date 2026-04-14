"""Tests for the Tag API endpoints.

These tests ensure that tags can be correctly created, retrieved, and updated
via the REST API endpoints.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import Tag

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """
    Helper to create a user and grant them a specific API permission.

    Args:
        permission_to_grant: The full permission codename (e.g. 'api.read_tag').

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
    ["api.params_api_read_tag", "api.params_api_read_objects"],
)
def test_get_tags(permission_to_grant):
    """Test retrieving a list of tags."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    Tag.objects.create(name="tag1", description="First tag")
    Tag.objects.create(name="tag2", description="Second tag")

    response = client.get("/api/v1/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["items"]) == 2

    names = [item["name"] for item in data["items"]]
    assert "tag1" in names
    assert "tag2" in names


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_tag", "api.params_api_create_objects"],
)
def test_create_tag(permission_to_grant):
    """Test creating a new tag."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    payload = {"name": "new-tag", "description": "A newly created tag"}
    response = client.post("/api/v1/tags", data=payload, content_type="application/json")

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["name"] == "new-tag"
    assert data["description"] == "A newly created tag"

    assert Tag.objects.filter(name="new-tag").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_tag", "api.params_api_create_objects"],
)
def test_create_tag_duplicate(permission_to_grant):
    """Test creating a tag that already exists returns 409."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    Tag.objects.create(name="existing-tag", description="Already exists")

    payload = {"name": "existing-tag", "description": "Duplicate attempt"}
    response = client.post("/api/v1/tags", data=payload, content_type="application/json")

    assert response.status_code == 409
    assert "already exists" in response.json()["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_tag", "api.params_api_update_objects"],
)
def test_update_tag(permission_to_grant):
    """Test updating an existing tag's description."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    tag = Tag.objects.create(name="updatable-tag", description="Old description")

    payload = {"description": "New description"}
    response = client.put(f"/api/v1/tags/{tag.name}", data=payload, content_type="application/json")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updatable-tag"
    assert data["description"] == "New description"

    tag.refresh_from_db()
    assert tag.description == "New description"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_tag", "api.params_api_update_objects"],
)
def test_update_tag_not_found(permission_to_grant):
    """Test updating a non-existent tag returns 404."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    payload = {"description": "Should fail"}
    response = client.put("/api/v1/tags/non-existent-tag", data=payload, content_type="application/json")

    assert response.status_code == 404
    assert "not found" in response.json()["message"]
