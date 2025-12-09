import enum

from ninja import Schema


class ChangeSetStatus(enum.StrEnum):
    DRAFT = "draft"
    COMMITTED = "committed"
    ABANDONED = "abandoned"


class ChangeSetCreateRequest(Schema):
    name: str
    description: str | None = None


class ChangeSetUpdateRequest(Schema):
    name: str | None = None
    description: str | None = None


class ChangeSetCoalesceRequest(Schema):
    target_changeset_id: int


class GroupCreateRequest(Schema):
    name: str
    description: str | None = None
    changeset_id: int


class GroupUpdateRequest(Schema):
    description: str | None = None
    changeset_id: int | None = None
