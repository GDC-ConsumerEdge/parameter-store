import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet

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
    ["api.params_api_read_changeset", "api.params_api_read_objects"],
)
def test_get_changeset_by_id(permission_to_grant):
    """Test retrieving a ChangeSet by its ID using specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="test-changeset-id-lookup",
        description="A test changeset for ID lookup",
        created_by=user,
    )

    client = Client()
    client.force_login(user)

    # Test get by ID
    response = client.get(f"/api/v1/changeset/id/{cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["id"] == cs.id
    assert data["name"] == cs.name

    # Test 404 ID
    response = client.get("/api/v1/changeset/id/999999")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_changeset", "api.params_api_read_objects"],
)
def test_get_changeset_by_name(permission_to_grant):
    """Test retrieving a ChangeSet by its name using specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs_name = ChangeSet.objects.create(
        name="test-changeset-name-lookup",
        description="A test changeset for name lookup",
        created_by=user,
    )

    client = Client()
    client.force_login(user)

    # Test get by Name
    response = client.get(f"/api/v1/changeset/name/{cs_name.name}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["id"] == cs_name.id
    assert data["name"] == cs_name.name

    # Test 404 Name
    response = client.get("/api/v1/changeset/name/nonexistent")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_changeset", "api.params_api_create_objects"],
)
def test_create_changeset(permission_to_grant):
    """Test creating a new ChangeSet via POST with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    client = Client()
    client.force_login(user)

    payload = {"name": "new-changeset", "description": "Created via API"}

    response = client.post("/api/v1/changeset", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "new-changeset"
    assert data["created_by"] == user.username
    assert data["status"] == ChangeSet.Status.DRAFT


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_changeset", "api.params_api_update_objects"],
)
def test_update_changeset(permission_to_grant):
    """Test updating an existing ChangeSet via PUT with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="original-name",
        description="original-desc",
        created_by=user,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user)

    payload = {"name": "updated-name", "description": "updated-desc"}

    response = client.put(f"/api/v1/changeset/{cs.id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "updated-name"

    cs.refresh_from_db()
    assert cs.name == "updated-name"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_changeset", "api.params_api_update_objects"],
)
def test_update_changeset_by_other_user(permission_to_grant):
    """Test updating another user's ChangeSet with specific and global permissions."""
    # Create creator user manually
    user1 = User.objects.create_user(username="user1", password="password")

    # Create updater user with helper
    user2 = setup_user_with_permission(permission_to_grant)
    user2.username = "user2"  # Ensure distinct username if helper defaults
    user2.save()

    cs = ChangeSet.objects.create(
        name="changeset-by-user1",
        description="original-desc",
        created_by=user1,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user2)

    payload = {"name": "updated-by-user2"}

    response = client.put(f"/api/v1/changeset/{cs.id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "updated-by-user2"
    assert data["created_by"] == user1.username


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_changeset", "api.params_api_update_objects"],
)
def test_update_changeset_partial(permission_to_grant):
    """Test partial update of a ChangeSet via PUT with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="original-name",
        description="original-desc",
        created_by=user,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user)

    payload = {"description": "new-desc-only"}

    response = client.put(f"/api/v1/changeset/{cs.id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "original-name"  # Name should not change
    assert data["description"] == "new-desc-only"

    cs.refresh_from_db()
    assert cs.name == "original-name"
    assert cs.description == "new-desc-only"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_changeset", "api.params_api_delete_objects"],
)
def test_delete_changeset(permission_to_grant):
    """Test deleting a ChangeSet via DELETE with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="changeset-to-delete",
        description="will be deleted",
        created_by=user,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/changeset/{cs.id}")
    assert response.status_code == 204, f"Failed with permission {permission_to_grant}: {response.content}"

    # Verify deletion
    assert not ChangeSet.objects.filter(id=cs.id).exists()
