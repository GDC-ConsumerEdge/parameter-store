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
API endpoints for managing Clusters.

This module provides the CRUD operations for Clusters, including support for:
- Retrieving live and historical cluster data.
- Creating and updating clusters within the context of a ChangeSet (drafts).
- Staging clusters for deletion.
- Resolving clusters by name or stable Entity ID (UUID).
"""

import uuid
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
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
from api.utils import paginate, require_permissions
from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    ClusterTag,
    CustomDataField,
    Group,
    Tag,
)

clusters_router = Router(tags=["Clusters"])


def _get_cluster_or_404(cluster_name: str):
    """
    Retrieves a live Cluster by name or returns a 404 error.

    Args:
        cluster_name: The unique name of the cluster.

    Returns:
        Cluster: The live cluster object if found.
        tuple: A (status_code, response_dict) tuple if not found.
    """
    try:
        return Cluster.objects.get(name=cluster_name, is_live=True)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}


def _generate_cluster_response(cluster: Cluster) -> ClusterResponse:
    """
    Constructs a ClusterResponse object from a Cluster model instance.

    Args:
        cluster: The Cluster model instance.

    Returns:
        ClusterResponse: The Pydantic response object populated with cluster data.
    """
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
    """
    Core logic for retrieving the history of a cluster by its stable Entity ID.

    Args:
        shared_entity_id: The stable unique identifier (UUID) for the cluster entity.
        limit: Pagination limit.
        offset: Pagination offset.

    Returns:
        ClusterHistoryResponse: A paginated list of historical cluster versions.
    """
    from django.db.models import Q

    qs = (
        Cluster.objects.with_related()
        .filter(Q(shared_entity_id=shared_entity_id) & (Q(is_live=True) | Q(obsoleted_by_changeset__isnull=False)))
        .select_related("obsoleted_by_changeset")
        .order_by("-is_live", "-created_at")
    )

    history_page = paginate(qs, limit, offset)

    out = []
    for c in history_page:
        metadata = HistoryMetadata(
            is_live=c.is_live,
            is_pending_deletion=c.is_pending_deletion,
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
    """
    Gets the history of a specific cluster by its name.

    Resolves the name to the current live entity's stable Entity ID to fetch the history trail.
    """
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
    """
    Gets the history of a specific cluster by its stable Entity ID (UUID).
    """
    return _get_cluster_history_logic(cluster_id, limit, offset)


@clusters_router.get(
    "/cluster/{cluster_name}",
    response={200: ClusterResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single cluster by name",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster_by_name(request: HttpRequest, cluster_name: str):
    """
    Gets a specific live cluster by its name.
    """
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
    """
    Gets a specific live cluster by its stable Entity ID (UUID).
    """
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
    """
    Retrieves a paginated list of live clusters.

    Returns view-only cluster objects and their associated metadata, including
    cluster group, fleet label, custom data, and cluster intent.
    """
    qs = Cluster.objects.with_related().filter(is_live=True)
    clusters = paginate(qs, limit, offset)

    out = (_generate_cluster_response(cluster) for cluster in clusters)
    return {"clusters": out, "count": clusters.count()}


def _resolve_group_in_changeset(group_name: str, changeset: ChangeSet) -> Group | tuple[int, dict[str, str]]:
    """Resolves a Group by name from live groups or drafts in the same ChangeSet.

    Rejects groups that are staged for deletion in the target ChangeSet with a 409 error.

    Args:
        group_name: The unique name of the group to resolve.
        changeset: The active DRAFT ChangeSet.

    Returns:
        The resolved Group instance, or a (status_code, response_dict) error tuple.
    """
    try:
        live_group = Group.objects.get(name=group_name, is_live=True)
        if Group.objects.filter(draft_of=live_group, changeset_id=changeset, is_pending_deletion=True).exists():
            return 409, {"message": f"Group '{group_name}' is staged for deletion in ChangeSet {changeset.id}."}
        return live_group
    except Group.DoesNotExist:
        try:
            draft_group = Group.objects.get(name=group_name, changeset_id=changeset, is_live=False)
            if draft_group.is_pending_deletion:
                return 409, {"message": f"Group '{group_name}' is staged for deletion in ChangeSet {changeset.id}."}
            return draft_group
        except Group.DoesNotExist:
            return 404, {"message": f"Group {group_name} not found."}


def _resolve_cluster_relations(
    payload: ClusterCreateRequest | ClusterUpdateRequest,
    changeset: ChangeSet,
) -> tuple[list[Group], list[Tag], dict[str, CustomDataField]] | tuple[int, dict[str, str]]:
    """Pre-resolves secondary groups, tags, and custom data fields referenced in a payload.

    Args:
        payload: The incoming cluster create or update request payload.
        changeset: The active DRAFT ChangeSet.

    Returns:
        A tuple of (secondary_groups, tags, data_fields), or a 404 error tuple.
    """
    secondary_groups: list[Group] = []
    if payload.secondary_groups is not None:
        seen_groups: set[str] = set()
        for group_name in payload.secondary_groups:
            if group_name in seen_groups:
                continue
            seen_groups.add(group_name)
            resolved_group = _resolve_group_in_changeset(group_name, changeset)
            if isinstance(resolved_group, tuple):
                return resolved_group
            secondary_groups.append(resolved_group)

    tags: list[Tag] = []
    if payload.tags is not None:
        seen_tags: set[str] = set()
        for tag_name in payload.tags:
            if tag_name in seen_tags:
                continue
            seen_tags.add(tag_name)
            try:
                tags.append(Tag.objects.get(name=tag_name))
            except Tag.DoesNotExist:
                return 404, {"message": f"Tag '{tag_name}' not found."}

    data_fields: dict[str, CustomDataField] = {}
    if payload.data is not None:
        for field_name in payload.data:
            try:
                data_fields[field_name] = CustomDataField.objects.get(name=field_name)
            except CustomDataField.DoesNotExist:
                return 404, {"message": f"Data field '{field_name}' not found."}

    return secondary_groups, tags, data_fields


def _apply_cluster_relations(
    cluster: Cluster,
    payload: ClusterCreateRequest | ClusterUpdateRequest,
    changeset: ChangeSet,
    secondary_groups: list[Group],
    tags: list[Tag],
    data_fields: dict[str, CustomDataField],
) -> None:
    """Applies secondary groups, tags, fleet labels, data, and intent to a draft Cluster.

    For `fleet_labels` and `data`:
    - Omitting the top-level field leaves existing records untouched.
    - Passing an empty collection (`{}` or `[]`) deletes all existing draft records for that collection.
    - Providing a key with a non-null value creates or updates that record.
    - Setting a key's value to `null` removes the record for that key.

    Args:
        cluster: The draft Cluster instance being created or updated.
        payload: The incoming cluster create or update request payload.
        changeset: The active DRAFT ChangeSet.
        secondary_groups: Pre-resolved secondary Group instances.
        tags: Pre-resolved Tag instances.
        data_fields: Pre-resolved CustomDataField instances keyed by field name.

    Raises:
        ValidationError: If any relation or custom data field fails validation.
    """
    if payload.secondary_groups is not None:
        cluster.secondary_groups.set(secondary_groups)

    if payload.tags is not None:
        ClusterTag.objects.filter(cluster=cluster, changeset_id=changeset, is_live=False).delete()
        for tag_obj in tags:
            cluster_tag = ClusterTag(
                cluster=cluster,
                tag=tag_obj,
                is_live=False,
                changeset_id=changeset,
            )
            cluster_tag.full_clean()
            cluster_tag.save()

    if payload.fleet_labels is not None:
        label_items = (
            list(payload.fleet_labels.items())
            if isinstance(payload.fleet_labels, dict)
            else [(item.key, item.value) for item in payload.fleet_labels]
        )
        if not label_items:
            ClusterFleetLabel.objects.filter(
                cluster=cluster,
                changeset_id=changeset,
                is_live=False,
            ).delete()
        else:
            for key, value in label_items:
                if value is None:
                    ClusterFleetLabel.objects.filter(
                        cluster=cluster,
                        key=key,
                        changeset_id=changeset,
                        is_live=False,
                    ).delete()
                    continue

                existing_label = ClusterFleetLabel.objects.filter(
                    cluster=cluster,
                    key=key,
                    changeset_id=changeset,
                    is_live=False,
                ).first()
                if existing_label is not None:
                    existing_label.value = value
                    existing_label.full_clean()
                    existing_label.save()
                else:
                    fleet_label = ClusterFleetLabel(
                        cluster=cluster,
                        key=key,
                        value=value,
                        is_live=False,
                        changeset_id=changeset,
                    )
                    fleet_label.full_clean()
                    fleet_label.save()

    if payload.data is not None:
        if not payload.data:
            ClusterData.objects.filter(
                cluster=cluster,
                changeset_id=changeset,
                is_live=False,
            ).delete()
        else:
            validation_errors: dict[str, list[ValidationError | str]] = defaultdict(list)
            for field_name, value in payload.data.items():
                field_obj = data_fields[field_name]
                if value is None:
                    ClusterData.objects.filter(
                        cluster=cluster,
                        field=field_obj,
                        changeset_id=changeset,
                        is_live=False,
                    ).delete()
                    continue

                existing_data = ClusterData.objects.filter(
                    cluster=cluster,
                    field=field_obj,
                    changeset_id=changeset,
                    is_live=False,
                ).first()
                target_data = (
                    existing_data
                    if existing_data is not None
                    else ClusterData(
                        cluster=cluster,
                        field=field_obj,
                        value=value,
                        is_live=False,
                        changeset_id=changeset,
                    )
                )
                target_data.value = value
                try:
                    target_data.full_clean()
                except ValidationError as e:
                    if hasattr(e, "error_dict"):
                        for err_key, err_list in e.error_dict.items():
                            key = field_name if err_key in ("field", "value") else f"{field_name}.{err_key}"
                            validation_errors[key].extend(err_list)
                    else:
                        validation_errors[field_name].extend(e.error_list)
                    continue
                target_data.save()

            if validation_errors:
                raise ValidationError(validation_errors)

    if payload.intent is not None:
        intent_values = payload.intent.model_dump(exclude_unset=True)
        existing_intent = ClusterIntent.objects.filter(cluster=cluster).first()
        if existing_intent is not None:
            for attr, val in intent_values.items():
                setattr(existing_intent, attr, val)
            existing_intent.is_live = False
            existing_intent.changeset_id = changeset
            existing_intent.full_clean()
            existing_intent.save()
        else:
            intent_obj = ClusterIntent(
                cluster=cluster,
                is_live=False,
                changeset_id=changeset,
                **intent_values,
            )
            intent_obj.full_clean()
            intent_obj.save()


@clusters_router.post(
    "/cluster",
    response={200: ClusterResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new Cluster",
)
@require_permissions("api.params_api_create_cluster", "api.params_api_create_objects")
def create_cluster(request: HttpRequest, payload: ClusterCreateRequest):
    """Creates a new Cluster draft within a ChangeSet.

    Validates that the provided `changeset_id` exists and is in DRAFT status, and resolves
    `group`, `secondary_groups`, `tags`, `fleet_labels`, `data`, and `intent` on the draft cluster.
    """
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    group_obj = _resolve_group_in_changeset(payload.group, changeset)
    if isinstance(group_obj, tuple):
        return group_obj

    resolved_relations = _resolve_cluster_relations(payload, changeset)
    if len(resolved_relations) == 2:
        return resolved_relations
    secondary_groups, tags, data_fields = resolved_relations

    with transaction.atomic():
        cluster = Cluster(
            name=payload.name,
            description=payload.description,
            group=group_obj,
            changeset_id=changeset,
        )
        cluster.full_clean()
        cluster.save()

        _apply_cluster_relations(cluster, payload, changeset, secondary_groups, tags, data_fields)

    cluster = Cluster.objects.with_related().get(pk=cluster.pk)
    return _generate_cluster_response(cluster)


@clusters_router.put(
    "/cluster/{cluster_name}",
    response={200: ClusterResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a Cluster by Name",
)
@require_permissions("api.params_api_update_cluster", "api.params_api_update_objects")
def update_cluster_by_name(request: HttpRequest, cluster_name: str, payload: ClusterUpdateRequest):
    """Updates a Cluster by name within a ChangeSet.

    If a draft already exists in the specified ChangeSet, it updates the draft; if a live version
    exists, it creates a new draft and locks the live version.
    For `data` and `fleet_labels`, providing a key creates or updates that key, omitting a key
    leaves it untouched, setting a key to `null` removes it, and passing an empty collection (`{}`
    or `[]`) removes all items in that collection. For `tags` and `secondary_groups`, providing a
    list replaces the set of items, and passing `[]` removes all items.
    """
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
    """Updates a Cluster by its stable Entity ID (UUID) within a ChangeSet.

    Prioritizes finding an existing draft for the ID; if none exists, falls back to the live
    version to create a new draft.
    For `data` and `fleet_labels`, providing a key creates or updates that key, omitting a key
    leaves it untouched, setting a key to `null` removes it, and passing an empty collection (`{}`
    or `[]`) removes all items in that collection. For `tags` and `secondary_groups`, providing a
    list replaces the set of items, and passing `[]` removes all items.
    """
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
    """
    Encapsulates the core logic for updating a cluster (handling drafts and locking).

    Args:
        cluster_obj: The cluster object (live or draft) to update.
        payload: The update payload containing new values and changeset_id.

    Returns:
        ClusterResponse or tuple: The updated cluster response or an error tuple.
    """
    try:
        changeset = ChangeSet.objects.get(id=payload.changeset_id)
        if changeset.status != ChangeSet.Status.DRAFT:
            return 409, {"message": f"ChangeSet {changeset.id} is not in DRAFT status."}
    except ChangeSet.DoesNotExist:
        return 404, {"message": f"ChangeSet {payload.changeset_id} not found."}

    needs_new_draft = False
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
            needs_new_draft = True
    else:
        # Case: cluster_obj is a draft but NOT in the requested changeset
        return 409, {"message": f"Cluster '{cluster_obj.name}' is already a draft in another ChangeSet."}

    new_group_obj: Group | None = None
    if payload.group is not None:
        resolved_group = _resolve_group_in_changeset(payload.group, changeset)
        if isinstance(resolved_group, tuple):
            return resolved_group
        new_group_obj = resolved_group

    resolved_relations = _resolve_cluster_relations(payload, changeset)
    if len(resolved_relations) == 2:
        return resolved_relations
    secondary_groups, tags, data_fields = resolved_relations

    with transaction.atomic():
        if needs_new_draft:
            cluster_obj = cluster_obj.create_draft(changeset)
            live_cluster = cluster_obj.draft_of
            live_cluster.is_locked = True
            live_cluster.locked_by_changeset = changeset
            live_cluster.save()

        if payload.description is not None:
            cluster_obj.description = payload.description
        if new_group_obj is not None:
            cluster_obj.group = new_group_obj

        cluster_obj.full_clean()
        cluster_obj.save()

        _apply_cluster_relations(cluster_obj, payload, changeset, secondary_groups, tags, data_fields)

    cluster_obj = Cluster.objects.with_related().get(pk=cluster_obj.pk)
    return _generate_cluster_response(cluster_obj)


@clusters_router.delete(
    "/cluster/{cluster_name}",
    response={200: MessageResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Stage a Cluster for Deletion by Name",
)
@require_permissions("api.params_api_delete_cluster", "api.params_api_delete_objects")
def delete_cluster_by_name(request: HttpRequest, cluster_name: str, changeset_id: int):
    """
    Stages a Cluster for deletion by name within a ChangeSet.
    """
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
    """
    Stages a Cluster for deletion by its stable Entity ID (UUID) within a ChangeSet.
    """
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
    """
    Encapsulates the core logic for staging a cluster for deletion.

    Args:
        cluster_obj: The cluster object (live or draft).
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
