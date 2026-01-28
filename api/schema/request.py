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
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this creation.")


class GroupUpdateRequest(Schema):
    """Schema for updating a parameter group."""

    description: str | None = Field(None, description="The new description for the group.")
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this update.")


class ClusterCreateRequest(Schema):
    """Schema for creating a new cluster."""

    name: str = Field(..., description="The unique name for the new cluster.")
    description: str | None = Field(None, description="An optional description of the cluster.")
    group: str = Field(..., description="The name of the primary group this cluster will belong to.")
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this creation.")


class ClusterUpdateRequest(Schema):
    """Schema for updating a cluster."""

    description: str | None = Field(None, description="The new description for the cluster.")
    group: str | None = Field(None, description="The name of a new primary group to move the cluster to.")
    changeset_id: int = Field(..., description="The ID of the active ChangeSet to associate with this update.")
