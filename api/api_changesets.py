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
API endpoints for managing ChangeSets.

This module provides the CRUD operations and lifecycle management for ChangeSets,
which allow for atomic staging and committing of changes to Clusters and Groups.
"""

from django.db.models import Prefetch
from django.http import HttpRequest
from ninja import Router
from ninja.responses import codes_4xx
from ninja.security import django_auth

from parameter_store.models import ChangeSet, Cluster, Group, GroupData

from .schema.request import (
    ChangeSetCoalesceRequest,
    ChangeSetCreateRequest,
    ChangeSetUpdateRequest,
)
from .schema.response import (
    ChangeAction,
    ChangeSetChangesResponse,
    ChangeSetResponse,
    ChangeSetsResponse,
    ClusterChangeItem,
    GroupChangeItem,
    GroupResponse,
    MessageResponse,
)
from .utils import paginate, require_permissions

changesets_router = Router()


def _generate_group_response(group: Group) -> GroupResponse:
    """
    Helper to construct GroupResponse from a Group model instance.

    Args:
        group: The Group model instance.

    Returns:
        GroupResponse: The Pydantic response object.
    """
    return GroupResponse(
        id=group.shared_entity_id,
        record_id=group.id,
        name=group.name,
        description=group.description,
        data={d.field.name: d.value for d in group.group_data.all()} if group.group_data.exists() else None,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _get_changeset_or_404(changeset_id: int = None, changeset_name: str = None):
    """
    Retrieves a ChangeSet by ID or name, returning the object or a 404 response.

    Args:
        changeset_id: Optional ID of the changeset.
        changeset_name: Optional name of the changeset.

    Returns:
        ChangeSet: The retrieved changeset instance.
        tuple: A (404, msg) tuple if not found.
    """
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
    """
    Helper to build ChangeSetResponse from a ChangeSet model instance.

    Args:
        cs: The ChangeSet model instance.

    Returns:
        ChangeSetResponse: The Pydantic response object.
    """
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
    """
    Retrieves a paginated list of ChangeSets, filtered by status.
    """
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
    """
    Creates a new ChangeSet in DRAFT status.
    """
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
    """
    Updates the metadata (name, description) of a DRAFT ChangeSet.
    """
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset  # Return 404 response

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
    """
    Retrieves a specific ChangeSet by its database ID.
    """
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
    """
    Retrieves a specific ChangeSet by its unique name.
    """
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
    """
    Abandons a ChangeSet and deletes all associated draft data.
    """
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
    """
    Commits a ChangeSet, making all staged changes live atomically.
    """
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset

    try:
        changeset.commit(request.user)
        return 200, {"message": f"ChangeSet '{changeset.name}' (ID: {changeset_id}) has been committed."}
    except ValueError as e:
        return 409, {"message": str(e)}


@changesets_router.get(
    "/changeset/{changeset_id}/changes",
    response={200: ChangeSetChangesResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get summary of changes in a ChangeSet",
)
@require_permissions("api.params_api_read_changeset", "api.params_api_read_objects")
def get_changeset_changes(request: HttpRequest, changeset_id: int):
    """
    Provides a structured summary of all provisional changes (Create/Update/Delete) in a ChangeSet.
    """
    changeset = _get_changeset_or_404(changeset_id=changeset_id)
    if isinstance(changeset, tuple):
        return changeset

    from .api_clusters import _generate_cluster_response

    # Fetch groups in this changeset
    groups = Group.objects.filter(changeset_id=changeset).prefetch_related(
        Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    )

    group_changes = []
    for g in groups:
        if g.is_pending_deletion:
            action = ChangeAction.DELETE
        elif g.draft_of_id is None:
            action = ChangeAction.CREATE
        else:
            action = ChangeAction.UPDATE

        group_changes.append(GroupChangeItem(action=action, entity=_generate_group_response(g)))

    # Fetch clusters in this changeset
    clusters = Cluster.objects.with_related().filter(changeset_id=changeset)

    cluster_changes = []
    for c in clusters:
        if c.is_pending_deletion:
            action = ChangeAction.DELETE
        elif c.draft_of_id is None:
            action = ChangeAction.CREATE
        else:
            action = ChangeAction.UPDATE

        cluster_changes.append(ClusterChangeItem(action=action, entity=_generate_cluster_response(c)))

    return ChangeSetChangesResponse(groups=group_changes, clusters=cluster_changes)


@changesets_router.post(
    "/changeset/{changeset_id}/coalesce",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Coalesce a ChangeSet",
)
@require_permissions("api.params_api_update_changeset", "api.params_api_update_objects")
def coalesce_changeset(request: HttpRequest, changeset_id: int, payload: ChangeSetCoalesceRequest):
    """
    Merges all changes from the current ChangeSet into another target ChangeSet.
    """
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
