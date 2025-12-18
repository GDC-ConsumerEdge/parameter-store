import uuid

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja.responses import codes_4xx, codes_5xx
from ninja.security import django_auth

from api.schema.request import ClusterCreateRequest, ClusterUpdateRequest
from api.schema.response import (
    ClusterHistoryItem,
    ClusterHistoryResponse,
    ClusterResponse,
    ClustersResponse,
    FleetLabelResponse,
    HistoryMetadata,
    MessageResponse,
)
from parameter_store.models import ChangeSet, Cluster, Group

from .utils import paginate, require_permissions

clusters_router = Router()


def _get_cluster_or_404(cluster_name: str):
    try:
        return Cluster.objects.get(name=cluster_name, is_live=True)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}


def _generate_cluster_response(cluster: Cluster) -> ClusterResponse:
    return ClusterResponse(
        id=cluster.shared_entity_id,
        record_id=cluster.id,
        name=cluster.name,
        description=cluster.description,
        group=cluster.group.name,
        secondary_groups=[g.name for g in cluster.secondary_groups.all()],
        tags=[tag.name for tag in cluster.tags.all()],
        fleet_labels=[FleetLabelResponse(key=fl.key, value=fl.value) for fl in cluster.fleet_labels.all()],
        intent=cluster.intent if hasattr(cluster, "intent") else None,
        data={d.field.name: d.value for d in cluster.cluster_data.all()} if cluster.cluster_data.exists() else None,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
    )


def _get_cluster_history_logic(shared_entity_id: uuid.UUID, limit: int, offset: int):
    qs = (
        Cluster.objects.with_related()
        .filter(shared_entity_id=shared_entity_id, is_live=False, obsoleted_by_changeset__isnull=False)
        .select_related("obsoleted_by_changeset")
        .order_by("-created_at")
    )

    history_page = paginate(qs, limit, offset)

    out = []
    for c in history_page:
        metadata = HistoryMetadata(
            obsoleted_at=c.obsoleted_by_changeset.committed_at if c.obsoleted_by_changeset else None,
            obsoleted_by_changeset_id=c.obsoleted_by_changeset.id if c.obsoleted_by_changeset else None,
            obsoleted_by_changeset_name=c.obsoleted_by_changeset.name if c.obsoleted_by_changeset else None,
        )
        entity = _generate_cluster_response(c)
        out.append(ClusterHistoryItem(metadata=metadata, entity=entity))

    return ClusterHistoryResponse(history=out, count=qs.count())


@clusters_router.get(
    "/cluster/{cluster_name}/history",
    response={200: ClusterHistoryResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get history of a cluster by name",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster_history_by_name(request: HttpRequest, cluster_name: str, limit: int = 250, offset: int = 0):
    """Gets the history of a specific cluster by its name (resolving via the current live entity)."""
    cluster_obj = _get_cluster_or_404(cluster_name)
    if isinstance(cluster_obj, tuple):
        return cluster_obj
    return _get_cluster_history_logic(cluster_obj.shared_entity_id, limit, offset)


@clusters_router.get(
    "/cluster/id/{cluster_id}/history",
    response={200: ClusterHistoryResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get history of a cluster by ID",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster_history_by_id(request: HttpRequest, cluster_id: uuid.UUID, limit: int = 250, offset: int = 0):
    """Gets the history of a specific cluster by its shared entity ID."""
    return _get_cluster_history_logic(cluster_id, limit, offset)


@clusters_router.get(
    "/cluster/{cluster_name}",
    response={200: ClusterResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single cluster by name",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster_by_name(request: HttpRequest, cluster_name: str):
    """Gets a specific cluster by its name."""
    try:
        c = Cluster.objects.with_related().get(name=cluster_name, is_live=True)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}
    except Cluster.MultipleObjectsReturned:
        raise HttpError(500, "multiple clusters found")

    return _generate_cluster_response(c)


@clusters_router.get(
    "/cluster/id/{cluster_id}",
    response={200: ClusterResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single cluster by ID",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster_by_id(request: HttpRequest, cluster_id: uuid.UUID):
    """Gets a specific cluster by its internal ID."""
    try:
        c = Cluster.objects.with_related().get(shared_entity_id=cluster_id, is_live=True)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}

    return _generate_cluster_response(c)


@clusters_router.get(
    "/clusters",
    response={200: ClustersResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get many clusters",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_clusters(request: HttpRequest, limit=250, offset=0):
    """This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    qs = Cluster.objects.with_related().filter(is_live=True)
    clusters = paginate(qs, limit, offset)

    out = (_generate_cluster_response(cluster) for cluster in clusters)
    return {"clusters": out, "count": clusters.count()}


@clusters_router.post(
    "/cluster",
    response={200: ClusterResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new Cluster",
)
@require_permissions("api.params_api_create_cluster", "api.params_api_create_objects")
def create_cluster(request: HttpRequest, payload: ClusterCreateRequest):
    """Creates a new Cluster. Validates that the provided ChangeSet exists and is a draft."""
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    try:
        group_obj = Group.objects.get(name=payload.group, is_live=True)
    except Group.DoesNotExist:
        return 404, {"message": f"Group {payload.group} not found."}

    cluster = Cluster(
        name=payload.name,
        description=payload.description,
        group=group_obj,
        changeset_id=changeset,
    )
    cluster.full_clean()
    cluster.save()

    return _generate_cluster_response(cluster)


@clusters_router.put(
    "/cluster/{cluster_name}",
    response={200: ClusterResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Cluster by Name",
)
@require_permissions("api.params_api_update_cluster", "api.params_api_update_objects")
def update_cluster_by_name(request: HttpRequest, cluster_name: str, payload: ClusterUpdateRequest):
    """Updates a Cluster by name. If changeset_id is provided, validates it."""
    cluster_obj = _get_cluster_or_404(cluster_name)
    if isinstance(cluster_obj, tuple) and payload.changeset_id:
        try:
            cluster_obj = Cluster.objects.get(name=cluster_name, changeset_id=payload.changeset_id, is_live=False)
        except Cluster.DoesNotExist:
            return 404, {"message": "cluster not found"}
    elif isinstance(cluster_obj, tuple):
        return cluster_obj

    return _update_cluster_logic(cluster_obj, payload)


@clusters_router.put(
    "/cluster/id/{cluster_id}",
    response={200: ClusterResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Cluster by ID",
)
@require_permissions("api.params_api_update_cluster", "api.params_api_update_objects")
def update_cluster_by_id(request: HttpRequest, cluster_id: uuid.UUID, payload: ClusterUpdateRequest):
    """Updates a Cluster by ID. If changeset_id is provided, validates it."""
    # Try to find a draft first
    try:
        cluster_obj = Cluster.objects.get(shared_entity_id=cluster_id, is_live=False, changeset_id__isnull=False)
    except Cluster.DoesNotExist:
        # If no draft, try to find live
        try:
            cluster_obj = Cluster.objects.get(shared_entity_id=cluster_id, is_live=True)
        except Cluster.DoesNotExist:
            return 404, {"message": "cluster not found"}

    return _update_cluster_logic(cluster_obj, payload)


def _update_cluster_logic(cluster_obj: Cluster, payload: ClusterUpdateRequest):
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    if cluster_obj.changeset_id == changeset:
        pass
    elif cluster_obj.is_live:
        if cluster_obj.is_locked:
            if cluster_obj.locked_by_changeset != changeset:
                return 409, {"message": f"Cluster is locked by another ChangeSet: {cluster_obj.locked_by_changeset.id}"}
            else:
                try:
                    draft_cluster = Cluster.objects.get(draft_of=cluster_obj, changeset_id=changeset)
                    cluster_obj = draft_cluster
                except Cluster.DoesNotExist:
                    return 500, {"message": "Inconsistent state: Locked by changeset but draft not found."}
        else:
            cluster_obj = cluster_obj.create_draft(changeset)
            live_cluster = cluster_obj.draft_of
            live_cluster.is_locked = True
            live_cluster.locked_by_changeset = changeset
            live_cluster.save()
    else:
        # Case: cluster_obj is a draft but NOT in the requested changeset
        return 409, {"message": f"Cluster '{cluster_obj.name}' is already a draft in another ChangeSet."}

    if payload.description is not None:
        cluster_obj.description = payload.description
    if payload.group is not None:
        try:
            group_obj = Group.objects.get(name=payload.group, is_live=True)
            cluster_obj.group = group_obj
        except Group.DoesNotExist:
            return 404, {"message": f"Group {payload.group} not found."}

    cluster_obj.full_clean()
    cluster_obj.save()

    return _generate_cluster_response(cluster_obj)


@clusters_router.delete(
    "/cluster/{cluster_name}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Cluster for Deletion by Name",
)
@require_permissions("api.params_api_delete_cluster", "api.params_api_delete_objects")
def delete_cluster_by_name(request: HttpRequest, cluster_name: str, changeset_id: int):
    """Stages a Cluster for deletion by name within a ChangeSet."""
    cluster_obj = _get_cluster_or_404(cluster_name)
    if isinstance(cluster_obj, tuple) and changeset_id:
        try:
            cluster_obj = Cluster.objects.get(name=cluster_name, changeset_id=changeset_id, is_live=False)
        except Cluster.DoesNotExist:
            return 404, {"message": "cluster not found"}
    elif isinstance(cluster_obj, tuple):
        return cluster_obj

    return _delete_cluster_logic(cluster_obj, changeset_id)


@clusters_router.delete(
    "/cluster/id/{cluster_id}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Cluster for Deletion by ID",
)
@require_permissions("api.params_api_delete_cluster", "api.params_api_delete_objects")
def delete_cluster_by_id(request: HttpRequest, cluster_id: uuid.UUID, changeset_id: int):
    """Stages a Cluster for deletion by ID within a ChangeSet."""
    # Try to find a draft first
    try:
        cluster_obj = Cluster.objects.get(shared_entity_id=cluster_id, is_live=False, changeset_id__isnull=False)
    except Cluster.DoesNotExist:
        # If no draft, try to find live
        try:
            cluster_obj = Cluster.objects.get(shared_entity_id=cluster_id, is_live=True)
        except Cluster.DoesNotExist:
            return 404, {"message": "cluster not found"}

    return _delete_cluster_logic(cluster_obj, changeset_id)


def _delete_cluster_logic(cluster_obj: Cluster, changeset_id: int):
    try:
        changeset = ChangeSet.objects.get(id=changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {changeset_id} not found."}

    if cluster_obj.is_locked:
        if cluster_obj.locked_by_changeset != changeset:
            return 409, {"message": f"Cluster is locked by another ChangeSet: {cluster_obj.locked_by_changeset.id}"}
        else:
            try:
                draft_cluster = Cluster.objects.get(draft_of=cluster_obj, changeset_id=changeset)
                draft_cluster.is_pending_deletion = True
                draft_cluster.save()
                return 200, {
                    "message": f"Cluster '{cluster_obj.name}' updated to pending deletion in ChangeSet {changeset_id}."
                }
            except Cluster.DoesNotExist:
                return 500, {"message": "Inconsistent state."}

    cluster_obj.create_draft(changeset, is_pending_deletion=True)

    cluster_obj.is_locked = True
    cluster_obj.locked_by_changeset = changeset
    cluster_obj.save()

    return 200, {"message": f"Cluster '{cluster_obj.name}' staged for deletion in ChangeSet {changeset_id}."}
