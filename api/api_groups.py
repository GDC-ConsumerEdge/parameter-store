from django.db.models import Prefetch
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja.responses import codes_4xx, codes_5xx
from ninja.security import django_auth

from parameter_store.models import ChangeSet, Group, GroupData

from .schema.request import GroupCreateRequest, GroupUpdateRequest
from .schema.response import (
    GroupResponse,
    GroupsResponse,
    MessageResponse,
)
from .utils import paginate, require_permissions

groups_router = Router()


def _get_group_or_404(group_name: str):
    try:
        return Group.objects.get(name=group_name, is_live=True)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}


def _update_group_logic(group_obj: Group, payload: GroupUpdateRequest):
    changeset = None
    if payload.changeset_id:
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
            # But we fetched it by name + changeset_id above, so this shouldn't be reached if we are careful.
            pass

    if payload.description is not None:
        group_obj.description = payload.description

    group_obj.full_clean()
    group_obj.save()

    return GroupResponse(
        name=group_obj.name,
        description=group_obj.description,
        data={d.field.name: d.value for d in group_obj.group_data.all()} if group_obj.group_data.exists() else None,
        created_at=group_obj.created_at,
        updated_at=group_obj.updated_at,
    )


def _delete_group_logic(group_obj: Group, changeset_id: int):
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
    """Gets a specific group by its name."""
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
        name=g.name,
        description=g.description,
        data={d.field.name: d.value for d in g.group_data.all()} if g.group_data.exists() else None,
        created_at=g.created_at,
        updated_at=g.updated_at,
    )


@groups_router.get(
    "/group/id/{group_id}",
    response={200: GroupResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single group by ID",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group_by_id(request: HttpRequest, group_id: int):
    """Gets a specific group by its internal ID."""
    try:
        g = Group.objects.prefetch_related(
            Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
        ).get(id=group_id)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}

    return GroupResponse(
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
    """Clusters belong to groups. This endpoint returns all available groups to which a cluster
    may belong.
    """
    # Query the for the groups while prefetching related data
    data_prefetch = Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    qs = Group.objects.prefetch_related(data_prefetch).filter(is_live=True).all()
    groups = paginate(qs, limit, offset)

    out = (
        GroupResponse(
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
    """Creates a new Group. If changeset_id is provided, checks if it exists and is a draft."""
    changeset = None
    if payload.changeset_id:
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
    """Updates a Group by name. If changeset_id is provided, validates it."""
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
    summary="Update a Group by ID",
)
@require_permissions("api.params_api_update_group", "api.params_api_update_objects")
def update_group_by_id(request: HttpRequest, group_id: int, payload: GroupUpdateRequest):
    """Updates a Group by ID. If changeset_id is provided, validates it."""
    try:
        group_obj = Group.objects.get(id=group_id)
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
    """Stages a Group for deletion by name within a ChangeSet."""
    group_obj = _get_group_or_404(group_name)
    if isinstance(group_obj, tuple):
        return group_obj

    return _delete_group_logic(group_obj, changeset_id)


@groups_router.delete(
    "/group/id/{group_id}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Group for Deletion by ID",
)
@require_permissions("api.params_api_delete_group", "api.params_api_delete_objects")
def delete_group_by_id(request: HttpRequest, group_id: int, changeset_id: int):
    """Stages a Group for deletion by ID within a ChangeSet."""
    try:
        group_obj = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}

    return _delete_group_logic(group_obj, changeset_id)
