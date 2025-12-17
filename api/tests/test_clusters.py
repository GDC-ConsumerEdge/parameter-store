import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from parameter_store.models import ChangeSet, Cluster, Group

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
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_cluster_by_name(permission_to_grant):
    """Test retrieving a Cluster by its name."""
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_cluster_by_id(permission_to_grant):
    """Test retrieving a Cluster by its ID."""
    user = setup_user_with_permission(permission_to_grant)
    group = Group.objects.create(name="test-group", is_live=True)
    c = Cluster.objects.create(name="test-cluster-id", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.get(f"/api/v1/cluster/id/{c.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"
    data = response.json()
    assert data["name"] == "test-cluster-id"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_read_cluster", "api.params_api_read_objects"],
)
def test_get_clusters_list(permission_to_grant):
    """Test retrieving a list of Clusters."""
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
    """Test that creating a Cluster without a changeset ID fails."""
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
    """Test that updating a Cluster without a changeset ID fails."""
    user = setup_user_with_permission(permission_to_grant)
    # Use shorter unique names
    suffix = permission_to_grant.split(".")[-1][:10]
    group = Group.objects.create(name=f"grp-up-no-cs-{suffix}", is_live=True)
    Cluster.objects.create(name="live-cluster", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated"}
    response = client.put("/api/v1/cluster/live-cluster", data=payload, content_type="application/json")
    # This currently FAILS (returns 200) because the API logic allows it.
    assert response.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_create_cluster", "api.params_api_create_objects"],
)
def test_create_cluster_with_changeset(permission_to_grant):
    """Test creating a new Cluster linked to a ChangeSet."""
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
    """Test updating an existing Cluster."""
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
    """Test updating an existing Cluster by ID."""
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="test-update-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    c = Cluster.objects.create(name="update-cluster-id", description="Original", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    payload = {"description": "Updated description via ID", "changeset_id": cs.id}
    response = client.put(f"/api/v1/cluster/id/{c.id}", data=payload, content_type="application/json")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    draft = Cluster.objects.get(draft_of=c, changeset_id=cs)
    assert draft.description == "Updated description via ID"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "permission_to_grant",
    ["api.params_api_delete_cluster", "api.params_api_delete_objects"],
)
def test_delete_cluster_api(permission_to_grant):
    """Test staging a Cluster for deletion via DELETE."""
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
    """Test staging a Cluster for deletion by ID."""
    user = setup_user_with_permission(permission_to_grant)
    cs = ChangeSet.objects.create(name="delete-id-cs", created_by=user, status=ChangeSet.Status.DRAFT)
    group = Group.objects.create(name="test-group", is_live=True)
    cluster = Cluster.objects.create(name="cluster-to-delete-id", group=group, is_live=True)

    client = Client()
    client.force_login(user)

    response = client.delete(f"/api/v1/cluster/id/{cluster.id}?changeset_id={cs.id}")
    assert response.status_code == 200, f"Failed with permission {permission_to_grant}: {response.content}"

    cluster.refresh_from_db()
    assert cluster.is_locked is True
    assert cluster.locked_by_changeset == cs

    draft = Cluster.objects.get(changeset_id=cs, draft_of=cluster)
    assert draft.is_pending_deletion is True
