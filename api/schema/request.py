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
Request schemas for the Parameter Store API.

This module defines the Pydantic/Ninja schemas used to validate incoming
JSON payloads for creating and updating Clusters, Groups, and ChangeSets.
"""

import enum

from ninja import Field, Schema
from ninja.orm import create_schema
from pydantic import field_validator

from parameter_store.models import ClusterIntent


def _normalize_subnet_vlans_value(value: str | list[str | int] | None) -> str | None:
    """Normalizes subnet_vlans input so empty strings or lists become None and lists become comma-separated."""
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if item is not None and str(item).strip() != ""]
        return ",".join(items) if items else None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


class FleetLabelRequest(Schema):
    """Schema representing a fleet-level label key-value pair."""

    key: str = Field(..., description="The label key.")
    value: str | None = Field(
        None,
        description="The label value. Set to null to remove an existing label with this key.",
    )


_ClusterIntentBaseSchema = create_schema(
    ClusterIntent,
    name="_ClusterIntentBaseSchema",
    exclude=("id", "cluster", "is_live", "changeset_id", "created_at", "updated_at"),
)

_ClusterIntentUpdateBaseSchema = create_schema(
    ClusterIntent,
    name="_ClusterIntentUpdateBaseSchema",
    exclude=("id", "cluster", "is_live", "changeset_id", "created_at", "updated_at"),
    optional_fields="__all__",
)


class ClusterIntentRequest(_ClusterIntentBaseSchema):
    """Schema for creating a cluster configuration intent (spec)."""

    subnet_vlans: str | list[str | int] | None = Field(
        None,
        description=(
            "A comma-separated string (e.g., '500,2100,2500') or list of VLAN IDs for secondary networks. "
            "Omit, set to null, or pass an empty string or empty list to store null."
        ),
    )

    @field_validator("subnet_vlans", mode="after")
    @classmethod
    def normalize_subnet_vlans(cls, value: str | list[str | int] | None) -> str | None:
        """Normalizes empty strings or lists to None and joins VLAN lists into a comma-separated string."""
        return _normalize_subnet_vlans_value(value)


class ClusterIntentUpdateRequest(_ClusterIntentUpdateBaseSchema):
    """Schema for partially updating a cluster configuration intent (spec)."""

    subnet_vlans: str | list[str | int] | None = Field(
        None,
        description=(
            "A comma-separated string (e.g., '500,2100,2500') or list of VLAN IDs for secondary networks. "
            "Omit to leave unchanged; set to null or pass an empty string or empty list to clear."
        ),
    )

    @field_validator("subnet_vlans", mode="after")
    @classmethod
    def normalize_subnet_vlans(cls, value: str | list[str | int] | None) -> str | None:
        """Normalizes empty strings or lists to None and joins VLAN lists into a comma-separated string."""
        return _normalize_subnet_vlans_value(value)


class ChangeSetStatus(enum.StrEnum):
    DRAFT = "draft"
    COMMITTED = "committed"
    ABANDONED = "abandoned"


class ChangeSetCreateRequest(Schema):
    """Schema for creating a new ChangeSet."""

    name: str = Field(
        ..., description="A unique, human-readable name for the ChangeSet. This name must be unique within the system."
    )
    description: str | None = Field(
        None, description="A detailed description of the ChangeSet's purpose and the changes it contains."
    )


class ChangeSetUpdateRequest(Schema):
    """Schema for updating an existing ChangeSet's metadata."""

    name: str | None = Field(None, description="A new name for the ChangeSet. Must be unique if provided.")
    description: str | None = Field(None, description="An updated description of the ChangeSet.")


class ChangeSetCoalesceRequest(Schema):
    """Schema for coalescing (merging) a ChangeSet into another."""

    target_changeset_id: int = Field(
        ...,
        description="The unique ID of the target ChangeSet where changes will be merged. The target must be in DRAFT state.",
    )


class GroupCreateRequest(Schema):
    """Schema for creating a new parameter group."""

    name: str = Field(..., description="The unique name for the new group.")
    description: str | None = Field(None, description="An optional description of the group's function or scope.")
    data: dict[str, str | None] | None = Field(
        None,
        description=(
            "Optional dictionary mapping registered CustomDataField names to values for the group. "
            "Keys with null values are ignored on creation."
        ),
    )
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this creation.")


class GroupUpdateRequest(Schema):
    """Schema for updating a parameter group."""

    description: str | None = Field(None, description="The new description for the group.")
    data: dict[str, str | None] | None = Field(
        None,
        description=(
            "Optional dictionary mapping registered CustomDataField names to values to update on the group. "
            "Providing a key creates or updates that key; omitting a key leaves its existing value untouched; "
            "setting a key to null removes that key; passing an empty dictionary ({}) removes all custom data "
            "from the group."
        ),
    )
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this update.")


class ClusterCreateRequest(Schema):
    """Schema for creating a new cluster."""

    name: str = Field(..., description="The unique name for the new cluster.")
    description: str | None = Field(None, description="An optional description of the cluster.")
    group: str = Field(
        ...,
        description="The name of the primary group this cluster will belong to (may be live or a draft in the same ChangeSet).",
    )
    secondary_groups: list[str] | None = Field(
        None,
        description="Optional list of secondary group names associated with this cluster.",
    )
    tags: list[str] | None = Field(
        None,
        description="Optional list of registered tag names to apply to this cluster.",
    )
    fleet_labels: list[FleetLabelRequest] | dict[str, str | None] | None = Field(
        None,
        description=(
            "Optional list of {key, value} objects or dictionary of key-value pairs for fleet-level labels "
            "assigned to the cluster."
        ),
    )
    data: dict[str, str | None] | None = Field(
        None,
        description="Optional dictionary mapping registered CustomDataField names to values for the cluster.",
    )
    intent: ClusterIntentRequest | None = Field(
        None, description="An optional configuration intent (spec) for the cluster."
    )
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this creation.")


class ClusterUpdateRequest(Schema):
    """Schema for updating a cluster."""

    description: str | None = Field(None, description="The new description for the cluster.")
    group: str | None = Field(
        None,
        description="The name of a new primary group to move the cluster to (may be live or a draft in the same ChangeSet).",
    )
    secondary_groups: list[str] | None = Field(
        None,
        description=(
            "Optional list of secondary group names to replace the cluster's secondary groups. "
            "Omit to leave unchanged; pass an empty list ([]) to remove all secondary groups."
        ),
    )
    tags: list[str] | None = Field(
        None,
        description=(
            "Optional list of registered tag names to replace the cluster's tags. "
            "Omit to leave unchanged; pass an empty list ([]) to remove all tags."
        ),
    )
    fleet_labels: list[FleetLabelRequest] | dict[str, str | None] | None = Field(
        None,
        description=(
            "Optional list of {key, value} objects or dictionary of key-value pairs to update fleet-level labels. "
            "Providing a key creates or updates that label; omitting a key leaves its existing value untouched; "
            "setting a key's value to null removes that label; passing an empty collection ({} or []) removes all "
            "fleet labels from the cluster."
        ),
    )
    data: dict[str, str | None] | None = Field(
        None,
        description=(
            "Optional dictionary mapping registered CustomDataField names to values to update on the cluster. "
            "Providing a key creates or updates that key; omitting a key leaves its existing value untouched; "
            "setting a key to null removes that key; passing an empty dictionary ({}) removes all custom data "
            "from the cluster."
        ),
    )
    intent: ClusterIntentUpdateRequest | None = Field(
        None,
        description=(
            "Optional configuration intent (spec) to create or partially update on the cluster. "
            "When updating an existing intent, only provided fields are modified; when creating a new intent on a "
            "cluster that does not yet have one, all required intent fields must be supplied."
        ),
    )
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this update.")


class TagCreateRequest(Schema):
    """Schema for creating a new tag."""

    name: str = Field(..., description="The unique name for the new tag.")
    description: str | None = Field(None, description="An optional description of the tag.")


class TagUpdateRequest(Schema):
    """Schema for updating an existing tag."""

    description: str | None = Field(None, description="The new description for the tag.")


class CustomDataFieldCreateRequest(Schema):
    """Schema for creating a new data field."""

    name: str = Field(..., description="The unique name for the new data field.")
    description: str | None = Field(None, description="An optional description of the data field.")


class CustomDataFieldUpdateRequest(Schema):
    """Schema for updating an existing data field."""

    name: str | None = Field(None, description="The new name for the data field.")
    description: str | None = Field(None, description="The new description for the data field.")
