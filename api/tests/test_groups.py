import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, Group

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """Helper to create a user and grant them a specific API permission."""
    user = User.objects.create_user(username="testuser", password="password")

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
    """Test retrieving a Group by its name."""
    user = setup_user_with_permission(permission_to_grant)
    Group.objects.create(name="test-group", description="A test group", is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get("/api/v1/group/test-group")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-group"
    assert data["description"] == "A test group"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_group", "api.params_api_read_objects"],
)
def test_get_groups_list(permission_to_grant):
    """Test retrieving a list of Groups."""
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
def test_create_group(permission_to_grant):
    """Test creating a new Group."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="test-create-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    payload = {"name": "new-group", "description": "Created via API", "changeset_id": cs.id}
    response = client.post("/api/v1/group", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    data = response.json()
    assert data["name"] == "new-group"
    assert Group.objects.filter(name="new-group").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_with_changeset(permission_to_grant):
    """Test creating a new Group linked to a ChangeSet."""
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
    """Test updating an existing Group."""
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
    ["api.params_api_create_group", "api.params_api_create_objects"],
)
def test_create_group_validation_error(permission_to_grant):
    """Test creating a new Group with invalid data triggers a validation error."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="test-validation-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    # Attempt to create a group with a name exceeding max_length=30
    payload = {
        "name": "a-very-very-long-group-name-that-exceeds-thirty-characters",
        "description": "Invalid group",
        "changeset_id": cs.id,
    }
    response = client.post("/api/v1/group", data=payload, content_type="application/json")

    assert response.status_code == 422
    data = response.json()
    assert "name" in data["message"]
    # The message might vary slightly depending on Django version/locale, but should mention max characters
    assert "ensure this value has at most 30 characters" in str(data["message"]["name"][0]).lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_group", "api.params_api_update_objects"],
)
def test_update_group_validation_error(permission_to_grant):
    """Test updating a Group with invalid data triggers a validation error."""
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-validation-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    Group.objects.create(name="valid-name", description="Original", is_live=False, changeset_id=cs)

    client = Client()
    client.force_login(user)

    # Attempt to update a group with a description exceeding max_length=255
    long_description = "a" * 256  # 256 characters long
    payload = {"description": long_description, "changeset_id": cs.id}
    response = client.put("/api/v1/group/valid-name", data=payload, content_type="application/json")

    assert response.status_code == 422
    data = response.json()
    assert "description" in data["message"]
    assert "ensure this value has at most 255 characters" in str(data["message"]["description"][0]).lower()
