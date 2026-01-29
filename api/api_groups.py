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
API endpoints for managing Groups.

This module provides the CRUD operations for Groups, including support for:
- Retrieving live and historical group data.
- Creating and updating groups within the context of a ChangeSet (drafts).
- Staging groups for deletion.
- Resolving groups by name or stable Entity ID (UUID).
"""

import uuid

from django.db.models import Prefetch
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja.responses import codes_4xx, codes_5xx
from ninja.security import django_auth

from parameter_store.models import ChangeSet, Group, GroupData

from .schema.request import GroupCreateRequest, GroupUpdateRequest
from .schema.response import (
    GroupHistoryItem,
    GroupHistoryResponse,
    GroupResponse,
    GroupsResponse,
    HistoryMetadata,
    MessageResponse,
)
from .utils import paginate, require_permissions

groups_router = Router(tags=["Groups"])


def _get_group_or_404(group_name: str):
    """
    Retrieves a live Group by name or returns a 404 response.

    Args:
        group_name: The unique name of the group.

    Returns:
        Group: The live group object if found.
        tuple: A (status_code, response_dict) tuple if not found.
    """
    try:
        return Group.objects.get(name=group_name, is_live=True)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}


def _get_group_history_logic(shared_entity_id: uuid.UUID, limit: int, offset: int):
    """
    Core logic for retrieving the history of a group by its stable Entity ID.

    Args:
        shared_entity_id: The stable unique identifier (UUID) for the group entity.
        limit: Pagination limit.
        offset: Pagination offset.

    Returns:
        GroupHistoryResponse: A paginated list of historical group versions.
    """
    qs = (
        Group.objects.filter(shared_entity_id=shared_entity_id, is_live=False, obsoleted_by_changeset__isnull=False)
        .select_related("obsoleted_by_changeset")
        .prefetch_related(Prefetch("group_data", queryset=GroupData.objects.select_related("field")))
        .order_by("-created_at")
    )

    history_page = paginate(qs, limit, offset)

    out = []
    for g in history_page:
        metadata = HistoryMetadata(
            obsoleted_at=g.obsoleted_by_changeset.committed_at if g.obsoleted_by_changeset else None,
            obsoleted_by_changeset_id=g.obsoleted_by_changeset.id if g.obsoleted_by_changeset else None,
            obsoleted_by_changeset_name=g.obsoleted_by_changeset.name if g.obsoleted_by_changeset else None,
        )
        entity = GroupResponse(
            id=g.shared_entity_id,
            record_id=g.id,
            name=g.name,
            description=g.description,
            data={d.field.name: d.value for d in g.group_data.all()} if g.group_data.exists() else None,
            created_at=g.created_at,
            updated_at=g.updated_at,
        )
        out.append(GroupHistoryItem(metadata=metadata, entity=entity))

    return GroupHistoryResponse(history=out, count=qs.count())


def _update_group_logic(group_obj: Group, payload: GroupUpdateRequest):
    """
    Encapsulates the core logic for updating a group (handling drafts and locking).

    Args:
        group_obj: The group object (live or draft) to update.
        payload: The update payload containing new values and changeset_id.

    Returns:
        GroupResponse or tuple: The updated group response or an error tuple.
    """
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    # If group_obj is already a draft in this changeset, we are good to go.
    if group_obj.changeset_id == changeset:
        pass
    # If group_obj is LIVE, we need to handle draft creation/locking
    elif group_obj.is_live:
        if group_obj.is_locked:
            # Check if locked by THIS changeset - if so, we can update the draft (conceptually)
            # If locked by another changeset -> 409
            if group_obj.locked_by_changeset != changeset:
                return 409, {"message": f"Group is locked by another ChangeSet: {group_obj.locked_by_changeset.id}"}

            try:
                draft_group = Group.objects.get(draft_of=group_obj, changeset_id=changeset)
                group_obj = draft_group  # Operate on the draft
            except Group.DoesNotExist:
                # Should not happen if locked by this changeset, but safeguard
                return 500, {"message": "Inconsistent state: Locked by changeset but draft not found."}
        else:
            # Not locked, create new draft
            group_obj = group_obj.create_draft(changeset)
            live_group = group_obj.draft_of
            live_group.is_locked = True
            live_group.locked_by_changeset = changeset
            live_group.save()
    else:
        # Case: group_obj is a draft but NOT in the requested changeset (e.g. name collision or wrong ID passed)
        # This will now fail because we require the changeset_id in the payload to match.
        return 409, {"message": f"Group '{group_obj.name}' is already a draft in another ChangeSet."}

    if payload.description is not None:
        group_obj.description = payload.description

    group_obj.full_clean()
    group_obj.save()

    return GroupResponse(
        id=group_obj.shared_entity_id,
        record_id=group_obj.id,
        name=group_obj.name,
        description=group_obj.description,
        data={d.field.name: d.value for d in group_obj.group_data.all()} if group_obj.group_data.exists() else None,
        created_at=group_obj.created_at,
        updated_at=group_obj.updated_at,
    )


def _delete_group_logic(group_obj: Group, changeset_id: int):
    """
    Encapsulates the core logic for staging a group for deletion.

    Args:
        group_obj: The group object (live or draft).
        changeset_id: The ID of the changeset to use.

    Returns:
        tuple: (200, success_msg) or (error_code, error_dict).
    """
    try:
        changeset = ChangeSet.objects.get(id=changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {changeset_id} not found."}

    if group_obj.is_locked:
        if group_obj.locked_by_changeset != changeset:
            return 409, {"message": f"Group is locked by another ChangeSet: {group_obj.locked_by_changeset.id}"}
        else:
            # Already locked by this changeset. Update existing draft to be deletion
            # Find draft
            try:
                draft_group = Group.objects.get(draft_of=group_obj, changeset_id=changeset)
                draft_group.is_pending_deletion = True
                draft_group.save()
                return 200, {
                    "message": f"Group '{group_obj.name}' updated to pending deletion in ChangeSet {changeset_id}."
                }
            except Group.DoesNotExist:
                return 500, {"message": "Inconsistent state."}

    # Not locked, create deletion draft
    group_obj.create_draft(changeset, is_pending_deletion=True)

    # Lock original
    group_obj.is_locked = True
    group_obj.locked_by_changeset = changeset
    group_obj.save()

    return 200, {"message": f"Group '{group_obj.name}' staged for deletion in ChangeSet {changeset_id}."}


@groups_router.get(
    "/group/{group_name}",
    response={200: GroupResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single group by name",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group_by_name(request: HttpRequest, group_name: str):
    """
    Returns the current live version of a group identified by name.
    """
    # Query the for the group, prefetch related data
    groups = Group.objects.prefetch_related(
        Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    ).filter(is_live=True)

    try:
        g = groups.get(name=group_name)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}
    except Group.MultipleObjectsReturned:
        raise HttpError(500, "multiple groups found")

    return GroupResponse(
        id=g.shared_entity_id,
        record_id=g.id,
        name=g.name,
        description=g.description,
        data={d.field.name: d.value for d in g.group_data.all()} if g.group_data.exists() else None,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


@groups_router.get(
    "/group/{group_name}/history",
    response={200: GroupHistoryResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get history of a group by name",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group_history_by_name(request: HttpRequest, group_name: str, limit: int = 250, offset: int = 0):
    """
    Retrieves the version history of a group identified by name.

    Resolves the name to the current live entity's stable Entity ID to fetch its full history trail.
    """
    group_obj = _get_group_or_404(group_name)
    if isinstance(group_obj, tuple):
        return group_obj
    return _get_group_history_logic(group_obj.shared_entity_id, limit, offset)


@groups_router.get(
    "/group/id/{group_id}/history",
    response={200: GroupHistoryResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get history of a group by Entity ID",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group_history_by_id(request: HttpRequest, group_id: uuid.UUID, limit: int = 250, offset: int = 0):
    """
    Retrieves the version history of a group by its stable Entity ID (UUID).
    """
    return _get_group_history_logic(group_id, limit, offset)


@groups_router.get(
    "/group/id/{group_id}",
    response={200: GroupResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single group by Entity ID",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group_by_id(request: HttpRequest, group_id: uuid.UUID):
    """
    Returns the current live version of a group identified by its stable Entity ID (UUID).
    """
    try:
        g = Group.objects.prefetch_related(
            Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
        ).get(shared_entity_id=group_id, is_live=True)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}

    return GroupResponse(
        id=g.shared_entity_id,
        record_id=g.id,
        name=g.name,
        description=g.description,
        data={d.field.name: d.value for d in g.group_data.all()} if g.group_data.exists() else None,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


@groups_router.get(
    "/groups", response={200: GroupsResponse, codes_4xx: MessageResponse}, auth=django_auth, summary="Get many groups"
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_groups(request: HttpRequest, limit: int = 250, offset: int = 0):
    """
    Retrieves a paginated list of all current live groups.
    """
    # Query the for the groups while prefetching related data
    data_prefetch = Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    qs = Group.objects.prefetch_related(data_prefetch).filter(is_live=True).all()
    groups = paginate(qs, limit, offset)

    out = (
        GroupResponse(
            id=group.shared_entity_id,
            record_id=group.id,
            name=group.name,
            description=group.description,
            data={d.field.name: d.value for d in group.group_data.all()} if group.group_data.exists() else None,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        for group in groups
    )
    return {"groups": out, "count": groups.count()}


@groups_router.post(
    "/group",
    response={200: GroupResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new Group",
)
@require_permissions("api.params_api_create_group", "api.params_api_create_objects")
def create_group(request: HttpRequest, payload: GroupCreateRequest):
    """
    Initializes a new Group entity within a ChangeSet.

    The group is created in a DRAFT state and will not be live until the ChangeSet is committed.
    """
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    group = Group(
        name=payload.name,
        description=payload.description,
        changeset_id=changeset,
    )
    group.full_clean()
    group.save()

    return GroupResponse(
        id=group.shared_entity_id,
        record_id=group.id,
        name=group.name,
        description=group.description,
        data=None,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@groups_router.put(
    "/group/{group_name}",
    response={200: GroupResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Group by Name",
)
@require_permissions("api.params_api_update_group", "api.params_api_update_objects")
def update_group_by_name(request: HttpRequest, group_name: str, payload: GroupUpdateRequest):
    """
    Modifies a group identified by name within a ChangeSet.

    Creates a draft version if one does not exist, or updates the existing draft in the specified ChangeSet.
    """
    group_obj = _get_group_or_404(group_name)

    # Check if we are trying to update a draft directly
    if isinstance(group_obj, tuple) and payload.changeset_id:
        # Try to find the draft in the changeset
        try:
            group_obj = Group.objects.get(name=group_name, changeset_id=payload.changeset_id, is_live=False)
        except Group.DoesNotExist:
            return 404, {"message": "group not found"}
    elif isinstance(group_obj, tuple):
        return group_obj

    return _update_group_logic(group_obj, payload)


@groups_router.put(
    "/group/id/{group_id}",
    response={200: GroupResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Group by Entity ID",
)
@require_permissions("api.params_api_update_group", "api.params_api_update_objects")
def update_group_by_id(request: HttpRequest, group_id: uuid.UUID, payload: GroupUpdateRequest):
    """
    Modifies a group identified by its stable Entity ID (UUID) within a ChangeSet.
    """
    # Try to find a draft first
    try:
        group_obj = Group.objects.get(shared_entity_id=group_id, is_live=False, changeset_id__isnull=False)
    except Group.DoesNotExist:
        # If no draft, try to find live
        try:
            group_obj = Group.objects.get(shared_entity_id=group_id, is_live=True)
        except Group.DoesNotExist:
            return 404, {"message": "group not found"}

    return _update_group_logic(group_obj, payload)


@groups_router.delete(
    "/group/{group_name}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Group for Deletion by Name",
)
@require_permissions("api.params_api_delete_group", "api.params_api_delete_objects")
def delete_group_by_name(request: HttpRequest, group_name: str, changeset_id: int):
    """
    Stages a group for deletion by name.
    """
    group_obj = _get_group_or_404(group_name)
    if isinstance(group_obj, tuple):
        return group_obj

    return _delete_group_logic(group_obj, changeset_id)


@groups_router.delete(
    "/group/id/{group_id}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Group for Deletion by Entity ID",
)
@require_permissions("api.params_api_delete_group", "api.params_api_delete_objects")
def delete_group_by_id(request: HttpRequest, group_id: uuid.UUID, changeset_id: int):
    """
    Stages a group for deletion by its stable Entity ID (UUID).
    """
    # Try to find a draft first
    try:
        group_obj = Group.objects.get(shared_entity_id=group_id, is_live=False, changeset_id__isnull=False)
    except Group.DoesNotExist:
        # If no draft, try to find live
        try:
            group_obj = Group.objects.get(shared_entity_id=group_id, is_live=True)
        except Group.DoesNotExist:
            return 404, {"message": "group not found"}

    return _delete_group_logic(group_obj, changeset_id)
