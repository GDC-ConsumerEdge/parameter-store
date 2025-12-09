from django.http import HttpRequest
from ninja import Router
from ninja.responses import codes_4xx
from ninja.security import django_auth

from parameter_store.models import ChangeSet

from .schema.request import (
    ChangeSetCoalesceRequest,
    ChangeSetCreateRequest,
    ChangeSetUpdateRequest,
)
from .schema.response import (
    ChangeSetResponse,
    ChangeSetsResponse,
    MessageResponse,
)
from .utils import paginate, require_permissions

changesets_router = Router()


def _get_changeset_or_404(changeset_id: int = None, changeset_name: str = None):
    """Helper to retrieve a ChangeSet by ID or name, returning the object or a 404 response."""
    qs = ChangeSet.objects.select_related("committed_by", "created_by")
    try:
        if changeset_id is not None:
            cs = qs.get(id=changeset_id)
        else:
            cs = qs.get(name=changeset_name)
        return cs
    except ChangeSet.DoesNotExist:
        return 404, {"message": "changeset not found"}


def _build_changeset_response(cs: ChangeSet) -> ChangeSetResponse:
    """Helper to build ChangeSetResponse from a ChangeSet model instance."""
    return ChangeSetResponse(
        id=cs.id,
        name=cs.name,
        description=cs.description,
        status=cs.status,
        created_by=cs.created_by.username,
        committed_by=cs.committed_by.username if cs.committed_by else None,
        created_at=cs.created_at,
        updated_at=cs.updated_at,
        committed_at=cs.committed_at,
    )


@changesets_router.get(
    "/changesets",
    response={200: ChangeSetsResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get ChangeSets",
)
@require_permissions("api.params_api_read_changeset", "api.params_api_read_objects")
def get_changesets(
    request: HttpRequest,
    status: ChangeSet.Status = ChangeSet.Status.DRAFT,
    limit: int = 250,
    offset: int = 0,
):
    """Provides view-only ChangeSet objects"""
    qs = ChangeSet.objects.filter(status=ChangeSet.Status(status)).select_related("committed_by", "created_by")
    changesets = paginate(qs, limit, offset)
    out = (_build_changeset_response(cs) for cs in changesets)
    return ChangeSetsResponse(changesets=list(out), count=changesets.count())


@changesets_router.post(
    "/changeset",
    response={200: ChangeSetResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new ChangeSet",
)
@require_permissions("api.params_api_create_changeset", "api.params_api_create_objects")
def create_changeset(request: HttpRequest, payload: ChangeSetCreateRequest):
    """Creates a new ChangeSet."""
    cs = ChangeSet(
        name=payload.name,
        description=payload.description,
        created_by=request.user,
        status=ChangeSet.Status.DRAFT,
    )
    cs.save()
    return _build_changeset_response(cs)


@changesets_router.put(
    "/changeset/{changeset_id}",
    response={200: ChangeSetResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a ChangeSet",
)
@require_permissions("api.params_api_update_changeset", "api.params_api_update_objects")
def update_changeset(request: HttpRequest, changeset_id: int, payload: ChangeSetUpdateRequest):
    """Updates an existing ChangeSet. Only DRAFT changesets can be updated."""
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset  # Return 404 response

    # Status check (retained as core business logic)
    if changeset.status != ChangeSet.Status.DRAFT:
        return 409, {"message": f"Cannot edit ChangeSet in status '{changeset.status}'."}

    if payload.name is not None:
        changeset.name = payload.name
    if payload.description is not None:
        changeset.description = payload.description

    changeset.save()
    return _build_changeset_response(changeset)


@changesets_router.get(
    "/changeset/id/{changeset_id}",
    response={200: ChangeSetResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get ChangeSet by ID",
)
@require_permissions("api.params_api_read_changeset", "api.params_api_read_objects")
def get_changeset_by_id(request: HttpRequest, changeset_id: int):
    """Gets a specific ChangeSet by its ID."""
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset  # Return 404 response
    return _build_changeset_response(changeset)


@changesets_router.get(
    "/changeset/name/{changeset_name}",
    response={200: ChangeSetResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get ChangeSet by Name",
)
@require_permissions("api.params_api_read_changeset", "api.params_api_read_objects")
def get_changeset_by_name(request: HttpRequest, changeset_name: str):
    """Gets a specific ChangeSet by its name."""
    changeset = _get_changeset_or_404(changeset_name=changeset_name)
    if isinstance(changeset, tuple):
        return changeset  # Return 404 response
    return _build_changeset_response(changeset)


@changesets_router.post(
    "/changeset/{changeset_id}/abandon",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Abandon a ChangeSet",
)
@require_permissions("api.params_api_delete_changeset", "api.params_api_delete_objects")
def abandon_changeset(request: HttpRequest, changeset_id: int):
    """Abandons a ChangeSet and deletes its associated draft data. Only DRAFT changesets can be abandoned."""
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset  # Return 404 response

    try:
        changeset.abandon()
        return 200, {"message": f"ChangeSet '{changeset.name}' (ID: {changeset_id}) has been abandoned."}
    except ValueError as e:
        return 409, {"message": str(e)}


@changesets_router.post(
    "/changeset/{changeset_id}/commit",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Commit a ChangeSet",
)
@require_permissions("api.params_api_update_changeset", "api.params_api_update_objects")
def commit_changeset(request: HttpRequest, changeset_id: int):
    """Commits a ChangeSet, applying all its changes to the live data. Only DRAFT changesets can be committed."""
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset

    try:
        changeset.commit(request.user)
        return 200, {"message": f"ChangeSet '{changeset.name}' (ID: {changeset_id}) has been committed."}
    except ValueError as e:
        return 409, {"message": str(e)}


@changesets_router.post(
    "/changeset/{changeset_id}/coalesce",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Coalesce a ChangeSet",
)
@require_permissions("api.params_api_update_changeset", "api.params_api_update_objects")
def coalesce_changeset(request: HttpRequest, changeset_id: int, payload: ChangeSetCoalesceRequest):
    """Coalesces (merges) this ChangeSet into a target ChangeSet. The source ChangeSet is deleted."""
    source_changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(source_changeset, tuple):
        return source_changeset

    target_changeset = _get_changeset_or_404(changeset_id=payload.target_changeset_id)
    if isinstance(target_changeset, tuple):
        return 404, {"message": f"Target ChangeSet {payload.target_changeset_id} not found."}

    try:
        source_changeset.coalesce(target_changeset)
        return 200, {
            "message": f"ChangeSet '{source_changeset.name}' has been coalesced into '{target_changeset.name}'."
        }
    except ValueError as e:
        return 409, {"message": str(e)}
