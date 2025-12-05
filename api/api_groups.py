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
        return Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}


@groups_router.get(
    "/group/{group}",
    response={200: GroupResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single group",
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_group(request: HttpRequest, group: str):
    """Gets a specific group by its name."""
    # Query the for the group, prefetch related data
    groups = Group.objects.prefetch_related(
        Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    ).filter()

    try:
        g = groups.get(name=group)
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
    "/groups", response={200: GroupsResponse, codes_4xx: MessageResponse}, auth=django_auth, summary="Get many groups"
)
@require_permissions("api.params_api_read_group", "api.params_api_read_objects")
def get_groups(request: HttpRequest, limit: int = 250, offset: int = 0):
    """Clusters belong to groups. This endpoint returns all available groups to which a cluster
    may belong.
    """
    # Query the for the groups while prefetching related data
    data_prefetch = Prefetch("group_data", queryset=GroupData.objects.select_related("field"))
    qs = Group.objects.prefetch_related(data_prefetch).all()
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
    "/group/{group}",
    response={200: GroupResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Group",
)
@require_permissions("api.params_api_update_group", "api.params_api_update_objects")
def update_group(request: HttpRequest, group: str, payload: GroupUpdateRequest):
    """Updates a Group. If changeset_id is provided, validates it."""
    group_obj = _get_group_or_404(group)
    if isinstance(group_obj, tuple):
        return group_obj

    changeset = None
    if payload.changeset_id:
        try:
            changeset = ChangeSet.objects.get(id=payload.changeset_id)
            if changeset.status != ChangeSet.Status.DRAFT:
                return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
        except ChangeSet.DoesNotExist:
            return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

        # Assign to changeset if provided
        group_obj.changeset_id = changeset

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
