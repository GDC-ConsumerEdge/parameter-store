import enum
from datetime import datetime
from typing import Any

from ninja import Schema
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


ClusterIntentResponse = create_schema(
    ClusterIntent, exclude=('id', 'cluster', 'created_at', 'updated_at'))


class LogicalExpression(enum.StrEnum):
    AND = 'and'
    OR = 'or'


class ClusterResponse(Schema):
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
    status: str = 'ok'


class GroupResponse(Schema):
    name: str
    description: str | None
    data: dict[str, str | None] | None
    created_at: datetime | None
    updated_at: datetime | None


class GroupsResponse(Schema):
    groups: list[GroupResponse]
    count: int
