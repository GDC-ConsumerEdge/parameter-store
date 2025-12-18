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
    name: str = Field(..., description="The unique human-readable name of the ChangeSet.")
    description: str | None = Field(None, description="Optional description of the ChangeSet's purpose.")


class ChangeSetUpdateRequest(Schema):
    name: str | None = Field(None, description="Updated name for the ChangeSet.")
    description: str | None = Field(None, description="Updated description for the ChangeSet.")


class ChangeSetCoalesceRequest(Schema):
    target_changeset_id: int = Field(..., description="The ID of the target ChangeSet to merge into.")


class GroupCreateRequest(Schema):
    name: str = Field(..., description="The unique name of the new group.")
    description: str | None = Field(None, description="Optional group description.")
    changeset_id: int = Field(..., description="The ID of the ChangeSet to record this creation in.")


class GroupUpdateRequest(Schema):
    description: str | None = Field(None, description="Updated group description.")
    changeset_id: int = Field(..., description="The ID of the ChangeSet to record this update in.")


class ClusterCreateRequest(Schema):
    name: str = Field(..., description="The unique name of the new cluster.")
    description: str | None = Field(None, description="Optional cluster description.")
    group: str = Field(..., description="The name of the primary group this cluster belongs to.")
    changeset_id: int = Field(..., description="The ID of the ChangeSet to record this creation in.")


class ClusterUpdateRequest(Schema):
    description: str | None = Field(None, description="Updated cluster description.")
    group: str | None = Field(None, description="Updated primary group name for the cluster.")
    changeset_id: int = Field(..., description="The ID of the ChangeSet to record this update in.")
