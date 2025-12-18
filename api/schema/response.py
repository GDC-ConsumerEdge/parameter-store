###############################################################################
# Copyright 2024 Google, LLC
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
    id: uuid.UUID = Field(..., description="The stable, unique Entity ID for the logical cluster entity.")
    record_id: int = Field(..., description="The unique database row ID for this specific version record.")
    name: str = Field(..., description="The name of the cluster.")
    description: str | None = Field(None, description="The cluster description.")
    group: str = Field(..., description="The name of the primary group the cluster belongs to.")
    secondary_groups: list[str] = Field(..., description="Names of secondary groups for the cluster.")
    tags: list[str] = Field(..., description="List of tags assigned to the cluster.")
    fleet_labels: list[FleetLabelResponse] = Field(..., description="Fleet-level labels for the cluster.")
    data: dict[str, str | None] | None = Field(None, description="Custom parameter data for the cluster.")
    intent: ClusterIntentResponse | None = Field(None, description="Configuration intent for the cluster.")
    created_at: datetime | None = Field(None, description="Timestamp of when this version was created.")
    updated_at: datetime | None = Field(None, description="Timestamp of the last update to this version.")


class ClustersResponse(Schema):
    clusters: list[ClusterResponse] = Field(..., description="The list of clusters.")
    count: int = Field(..., description="Total count of clusters matching the query.")


class HealthResponse(Schema):
    status: str = Field(..., description="Service health status.")
    database: dict[str, Any] | None = Field(None, description="Database connection health details.")


class PingResponse(Schema):
    status: str = Field("ok", description="Connectivity check status.")


class GroupResponse(Schema):
    id: uuid.UUID = Field(..., description="The stable, unique Entity ID for the logical group entity.")
    record_id: int = Field(..., description="The unique database row ID for this specific version record.")
    name: str = Field(..., description="The name of the group.")
    description: str | None = Field(None, description="The group description.")
    data: dict[str, str | None] | None = Field(None, description="Custom parameter data for the group.")
    created_at: datetime | None = Field(None, description="Timestamp of when this version was created.")
    updated_at: datetime | None = Field(None, description="Timestamp of the last update to this version.")


class GroupsResponse(Schema):
    groups: list[GroupResponse] = Field(..., description="The list of groups.")
    count: int = Field(..., description="Total count of groups matching the query.")


class ChangeSetResponse(Schema):
    id: int = Field(..., description="The unique ID of the ChangeSet.")
    name: str = Field(..., description="The human-readable name of the ChangeSet.")
    description: str | None = Field(None, description="Optional description of the ChangeSet's purpose.")
    status: str = Field(..., description="The current status (DRAFT, COMMITTED, ABANDONED).")
    created_by: str = Field(..., description="Username of the user who created the ChangeSet.")
    committed_by: str | None = Field(None, description="Username of the user who committed the ChangeSet.")
    created_at: datetime | None = Field(None, description="Creation timestamp.")
    updated_at: datetime | None = Field(None, description="Last update timestamp.")
    committed_at: datetime | None = Field(None, description="Timestamp of when the ChangeSet was committed.")


class ChangeSetsResponse(Schema):
    changesets: list[ChangeSetResponse] = Field(..., description="The list of ChangeSets.")
    count: int = Field(..., description="Total count of ChangeSets.")


class ChangeAction(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class GroupChangeItem(Schema):
    action: ChangeAction = Field(..., description="The type of change performed on the group.")
    entity: GroupResponse = Field(..., description="The resulting state of the group entity.")


class ClusterChangeItem(Schema):
    action: ChangeAction = Field(..., description="The type of change performed on the cluster.")
    entity: ClusterResponse = Field(..., description="The resulting state of the cluster entity.")


class ChangeSetChangesResponse(Schema):
    groups: list[GroupChangeItem] = Field(..., description="List of group changes in this ChangeSet.")
    clusters: list[ClusterChangeItem] = Field(..., description="List of cluster changes in this ChangeSet.")


class HistoryMetadata(Schema):
    obsoleted_at: datetime | None = Field(None, description="When this version was obsoleted by a newer live version.")
    obsoleted_by_changeset_id: int | None = Field(
        None, description="The ID of the ChangeSet that obsoleted this version."
    )
    obsoleted_by_changeset_name: str | None = Field(
        None, description="The name of the ChangeSet that obsoleted this version."
    )


class GroupHistoryItem(Schema):
    metadata: HistoryMetadata = Field(..., description="Metadata about this historical version.")
    entity: GroupResponse = Field(..., description="The state of the group in this version.")


class ClusterHistoryItem(Schema):
    metadata: HistoryMetadata = Field(..., description="Metadata about this historical version.")
    entity: ClusterResponse = Field(..., description="The state of the cluster in this version.")


class GroupHistoryResponse(Schema):
    history: list[GroupHistoryItem] = Field(..., description="The chronological history of the group.")
    count: int = Field(..., description="Total number of historical versions.")


class ClusterHistoryResponse(Schema):
    history: list[ClusterHistoryItem] = Field(..., description="The chronological history of the cluster.")
    count: int = Field(..., description="Total number of historical versions.")
