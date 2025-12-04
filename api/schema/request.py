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
