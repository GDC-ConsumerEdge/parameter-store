import enum
import uuid
from datetime import datetime
from typing import Any

from ninja import Field, Schema
from ninja.orm import create_schema

from parameter_store.models import ClusterIntent


class MessageResponse(Schema):
    message: str


class ClusterTagResponse(Schema):
    name: str


class NameDescResponse(Schema):
    name: str
    description: str | None


class FleetLabelResponse(Schema):
    key: str
    value: str


ClusterIntentResponse: Schema = create_schema(ClusterIntent, exclude=("id", "cluster", "created_at", "updated_at"))


class LogicalExpression(enum.StrEnum):
    AND = "and"
    OR = "or"


class ClusterResponse(Schema):
    id: uuid.UUID = Field(..., description="The stable, unique identifier for the logical cluster entity.")
    record_id: int = Field(..., description="The unique identifier for this specific version record.")
    name: str
    description: str | None
    group: str
    secondary_groups: list[str]
    tags: list[str]
    fleet_labels: list[FleetLabelResponse]
    data: dict[str, str | None] | None
    intent: ClusterIntentResponse | None
    created_at: datetime | None
    updated_at: datetime | None


class ClustersResponse(Schema):
    clusters: list[ClusterResponse]
    count: int


class HealthResponse(Schema):
    status: str
    database: dict[str, Any] | None


class PingResponse(Schema):
    status: str = "ok"


class GroupResponse(Schema):
    id: uuid.UUID = Field(..., description="The stable, unique identifier for the logical group entity.")
    record_id: int = Field(..., description="The unique identifier for this specific version record.")
    name: str
    description: str | None
    data: dict[str, str | None] | None
    created_at: datetime | None
    updated_at: datetime | None


class GroupsResponse(Schema):
    groups: list[GroupResponse]
    count: int


class ChangeSetResponse(Schema):
    id: int
    name: str
    description: str | None
    status: str
    created_by: str
    committed_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    committed_at: datetime | None
    #
    # class Config:
    #     extra = 'ignore'


class ChangeSetsResponse(Schema):
    changesets: list[ChangeSetResponse]
    count: int


class ChangeAction(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class GroupChangeItem(Schema):
    action: ChangeAction
    entity: GroupResponse


class ClusterChangeItem(Schema):
    action: ChangeAction
    entity: ClusterResponse


class ChangeSetChangesResponse(Schema):
    groups: list[GroupChangeItem]
    clusters: list[ClusterChangeItem]


class HistoryMetadata(Schema):
    obsoleted_at: datetime | None
    obsoleted_by_changeset_id: int | None
    obsoleted_by_changeset_name: str | None


class GroupHistoryItem(Schema):
    metadata: HistoryMetadata
    entity: GroupResponse


class ClusterHistoryItem(Schema):
    metadata: HistoryMetadata
    entity: ClusterResponse


class GroupHistoryResponse(Schema):
    history: list[GroupHistoryItem]
    count: int


class ClusterHistoryResponse(Schema):
    history: list[ClusterHistoryItem]
    count: int
