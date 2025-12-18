import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet

User = get_user_model()


def setup_user_with_permission(permission_to_grant):
    """Helper to create a user and grant them a specific API permission."""
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
    ["api.params_api_read_changeset", "api.params_api_read_objects"],
)
def test_get_changeset_changes(permission_to_grant):
    """Test retrieving the summary of changes in a ChangeSet."""
    from parameter_store.models import Cluster, Group

    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(name="Summary Test", created_by=user)

    # --- Groups ---
    # 1. Create a new draft group (CREATE)
    Group.objects.create(name="new-group-1", changeset_id=cs, is_live=False)

    # 2. Create another new draft group (CREATE)
    Group.objects.create(name="new-group-2", changeset_id=cs, is_live=False)

    # 3. Create a draft of an existing group (UPDATE)
    live_group_update = Group.objects.create(name="update-group", is_live=True)
    Group.objects.create(
        name="update-group",
        draft_of=live_group_update,
        changeset_id=cs,
        is_live=False,
        shared_entity_id=live_group_update.shared_entity_id,
    )

    # 4. Create a deletion draft of an existing group (DELETE)
    live_group_delete = Group.objects.create(name="delete-group", is_live=True)
    Group.objects.create(
        name="delete-group",
        draft_of=live_group_delete,
        changeset_id=cs,
        is_live=False,
        shared_entity_id=live_group_delete.shared_entity_id,
        is_pending_deletion=True,
    )

    # --- Clusters ---
    base_group = Group.objects.create(name="base-group", is_live=True)

    # 5. Create a new draft cluster (CREATE)
    Cluster.objects.create(name="new-cluster-1", group=base_group, changeset_id=cs, is_live=False)

    # 6. Create a draft of an existing cluster (UPDATE)
    live_cluster_update = Cluster.objects.create(name="update-cluster", group=base_group, is_live=True)
    Cluster.objects.create(
        name="update-cluster",
        group=base_group,
        draft_of=live_cluster_update,
        changeset_id=cs,
        is_live=False,
        shared_entity_id=live_cluster_update.shared_entity_id,
    )

    # 7. Create a deletion draft of an existing cluster (DELETE)
    live_cluster_delete = Cluster.objects.create(name="delete-cluster", group=base_group, is_live=True)
    Cluster.objects.create(
        name="delete-cluster",
        group=base_group,
        draft_of=live_cluster_delete,
        changeset_id=cs,
        is_live=False,
        shared_entity_id=live_cluster_delete.shared_entity_id,
        is_pending_deletion=True,
    )

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/changeset/{cs.id}/changes")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()

    assert len(data["groups"]) == 4
    assert len(data["clusters"]) == 3

    group_actions = [g["action"] for g in data["groups"]]
    assert group_actions.count("create") == 2
    assert group_actions.count("update") == 1
    assert group_actions.count("delete") == 1

    cluster_actions = [c["action"] for c in data["clusters"]]
    assert cluster_actions.count("create") == 1
    assert cluster_actions.count("update") == 1
    assert cluster_actions.count("delete") == 1


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
def test_abandon_changeset(permission_to_grant):
    """Test abandoning a DRAFT ChangeSet via POST with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="changeset-to-abandon",
        description="will be abandoned",
        created_by=user,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user)

    response = client.post(f"/api/v1/changeset/{cs.id}/abandon")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cs.refresh_from_db()
    assert cs.status == ChangeSet.Status.ABANDONED

    # Test abandoning a non-DRAFT changeset
    cs.status = ChangeSet.Status.COMMITTED
    cs.save()
    response = client.post(f"/api/v1/changeset/{cs.id}/abandon")
    assert response.status_code == 409
    assert "not in draft state" in response.json()["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_changeset", "api.params_api_delete_objects"],
)
def test_abandon_changeset_404(permission_to_grant):
    """Test abandoning a non-existent ChangeSet returns 404."""
    user = setup_user_with_permission(permission_to_grant)
    client = Client()
    client.force_login(user)

    response = client.post("/api/v1/changeset/999999/abandon")
    assert response.status_code == 404
    assert "changeset not found" in response.json()["message"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_changeset", "api.params_api_update_objects"],
)
def test_commit_changeset_api(permission_to_grant):
    """Test committing a ChangeSet via POST with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    cs = ChangeSet.objects.create(
        name="changeset-to-commit",
        created_by=user,
        status=ChangeSet.Status.DRAFT,
    )

    client = Client()
    client.force_login(user)

    response = client.post(f"/api/v1/changeset/{cs.id}/commit")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cs.refresh_from_db()
    assert cs.status == ChangeSet.Status.COMMITTED
    assert cs.committed_by == user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_update_changeset", "api.params_api_update_objects"],
)
def test_coalesce_changeset_api(permission_to_grant):
    """Test coalescing a ChangeSet via POST with specific and global permissions."""
    user = setup_user_with_permission(permission_to_grant)

    source_cs = ChangeSet.objects.create(name="source-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    target_cs = ChangeSet.objects.create(name="target-cs", created_by=user, status=ChangeSet.Status.DRAFT)

    client = Client()
    client.force_login(user)

    payload = {"target_changeset_id": target_cs.id}
    response = client.post(f"/api/v1/changeset/{source_cs.id}/coalesce", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    # Source should be deleted
    assert not ChangeSet.objects.filter(id=source_cs.id).exists()
    # Target should remain
    assert ChangeSet.objects.filter(id=target_cs.id).exists()
