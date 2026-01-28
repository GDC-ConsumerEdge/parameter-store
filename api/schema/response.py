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
Response schemas for the Parameter Store API.

This module defines the Pydantic/Ninja schemas used to structure the JSON
responses for Clusters, Groups, ChangeSets, and their respective histories.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from ninja import Field, Schema
from ninja.orm import create_schema

from parameter_store.models import ClusterIntent


class MessageResponse(Schema):
    message: str = Field(..., description="A simple informational or error message.")


class ClusterTagResponse(Schema):
    name: str = Field(..., description="The name of the cluster tag.")


class NameDescResponse(Schema):
    """Schema representing a name-description pair."""

    name: str = Field(..., description="A unique name.")
    description: str | None = Field(None, description="An optional description.")


class FleetLabelResponse(Schema):
    key: str = Field(..., description="The label key.")
    value: str = Field(..., description="The label value.")


ClusterIntentResponse: Schema = create_schema(ClusterIntent, exclude=("id", "cluster", "created_at", "updated_at"))


class LogicalExpression(enum.StrEnum):
    AND = "and"
    OR = "or"


class ClusterResponse(Schema):
    """Schema representing a Cluster entity."""

    id: uuid.UUID = Field(
        ...,
        description="The immutable, unique UUID for the logical cluster entity. This ID remains constant across versions.",
    )
    record_id: int = Field(..., description="The unique integer ID for this specific version record in the database.")
    name: str = Field(..., description="The unique name of the cluster.")
    description: str | None = Field(None, description="An optional description of the cluster.")
    group: str = Field(..., description="The name of the primary group associated with this cluster.")
    secondary_groups: list[str] = Field(
        ..., description="A list of names of secondary groups associated with this cluster."
    )
    tags: list[str] = Field(..., description="A list of tags applied to this cluster.")
    fleet_labels: list[FleetLabelResponse] = Field(
        ..., description="A list of fleet-level labels assigned to the cluster."
    )
    data: dict[str, str | None] | None = Field(
        None, description="A dictionary of custom parameter data for the cluster."
    )
    intent: ClusterIntentResponse | None = Field(
        None, description="The configuration intent (spec) for the cluster, if available."
    )
    created_at: datetime | None = Field(None, description="The timestamp when this specific version was created.")
    updated_at: datetime | None = Field(None, description="The timestamp of the last update to this version.")


class ClustersResponse(Schema):
    clusters: list[ClusterResponse] = Field(..., description="The list of clusters matching the query.")
    count: int = Field(..., description="The total number of clusters matching the query (for pagination).")


class HealthResponse(Schema):
    status: str = Field(..., description="The overall health status of the service.")
    database: dict[str, Any] | None = Field(None, description="Details about the database connection health.")


class PingResponse(Schema):
    status: str = Field("ok", description="The connectivity check status (always 'ok' if reachable).")


class GroupResponse(Schema):
    """Schema representing a Group entity."""

    id: uuid.UUID = Field(..., description="The immutable, unique UUID for the logical group entity.")
    record_id: int = Field(..., description="The unique integer ID for this specific version record in the database.")
    name: str = Field(..., description="The unique name of the group.")
    description: str | None = Field(None, description="An optional description of the group.")
    data: dict[str, str | None] | None = Field(None, description="A dictionary of custom parameter data for the group.")
    created_at: datetime | None = Field(None, description="The timestamp when this specific version was created.")
    updated_at: datetime | None = Field(None, description="The timestamp of the last update to this version.")


class GroupsResponse(Schema):
    groups: list[GroupResponse] = Field(..., description="The list of groups matching the query.")
    count: int = Field(..., description="The total number of groups matching the query.")


class ChangeSetResponse(Schema):
    """Schema representing a ChangeSet."""

    id: int = Field(..., description="The unique database ID of the ChangeSet.")
    name: str = Field(..., description="The human-readable name of the ChangeSet.")
    description: str | None = Field(None, description="A description of the ChangeSet's purpose.")
    status: str = Field(
        ..., description="The current status of the ChangeSet (e.g., 'draft', 'committed', 'abandoned')."
    )
    created_by: str = Field(..., description="The username of the user who created the ChangeSet.")
    committed_by: str | None = Field(
        None, description="The username of the user who committed the ChangeSet (if committed)."
    )
    created_at: datetime | None = Field(None, description="The timestamp when the ChangeSet was created.")
    updated_at: datetime | None = Field(None, description="The timestamp when the ChangeSet was last updated.")
    committed_at: datetime | None = Field(None, description="The timestamp when the ChangeSet was committed.")


class ChangeSetsResponse(Schema):
    changesets: list[ChangeSetResponse] = Field(..., description="The list of ChangeSets matching the query.")
    count: int = Field(..., description="The total number of ChangeSets matching the query.")


class ChangeAction(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class GroupChangeItem(Schema):
    action: ChangeAction = Field(..., description="The type of change performed (create, update, delete).")
    entity: GroupResponse = Field(..., description="The full state of the group entity resulting from the change.")


class ClusterChangeItem(Schema):
    action: ChangeAction = Field(..., description="The type of change performed (create, update, delete).")
    entity: ClusterResponse = Field(..., description="The full state of the cluster entity resulting from the change.")


class ChangeSetChangesResponse(Schema):
    groups: list[GroupChangeItem] = Field(..., description="A list of changes affecting groups in this ChangeSet.")
    clusters: list[ClusterChangeItem] = Field(
        ..., description="A list of changes affecting clusters in this ChangeSet."
    )


class HistoryMetadata(Schema):
    """Metadata for a historical version of an entity."""

    obsoleted_at: datetime | None = Field(
        None, description="The timestamp when this version was obsoleted by a newer version."
    )
    obsoleted_by_changeset_id: int | None = Field(
        None, description="The ID of the ChangeSet that introduced the new version, obsoleting this one."
    )
    obsoleted_by_changeset_name: str | None = Field(
        None, description="The name of the ChangeSet that introduced the new version, obsoleting this one."
    )


class GroupHistoryItem(Schema):
    metadata: HistoryMetadata = Field(..., description="Metadata describing the lifecycle of this historical version.")
    entity: GroupResponse = Field(..., description="The state of the group in this specific historical version.")


class ClusterHistoryItem(Schema):
    metadata: HistoryMetadata = Field(..., description="Metadata describing the lifecycle of this historical version.")
    entity: ClusterResponse = Field(..., description="The state of the cluster in this specific historical version.")


class GroupHistoryResponse(Schema):
    history: list[GroupHistoryItem] = Field(..., description="The chronological history of the group's versions.")
    count: int = Field(..., description="The total number of historical versions returned.")


class ClusterHistoryResponse(Schema):
    history: list[ClusterHistoryItem] = Field(..., description="The chronological history of the cluster's versions.")
    count: int = Field(..., description="The total number of historical versions returned.")
