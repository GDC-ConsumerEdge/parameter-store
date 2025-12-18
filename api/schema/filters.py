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
Filter schemas for the Parameter Store API.

This module defines Pydantic/Ninja FilterSchemas used for advanced filtering
capabilities on list endpoints (e.g., filtering clusters by tag or update time).
"""

from datetime import datetime
from typing import Annotated, Any

import pydantic
from django.db.models import Q
from ninja import FilterSchema
from pydantic import Field

from api.schema.response import LogicalExpression


class ClusterFilter(FilterSchema):
    group: Annotated[
        str | None,
        Field(q=["group__name", "secondary_groups__name"], description="Cluster group to match; accepts only one"),
    ] = None

    tags: Annotated[
        str | None,
        Field(
            q="tags__name",
            description="Comma-separated list of clusters tags; set tags_logical_operator "
            "to define how tags are to be queried",
        ),
    ] = None

    # tags_expression should be ignored in a filter expression and is only used to define
    # how tag queries are to be performed, either with a logical AND or OR
    # this field is popped out of the generated filter in overridden `get_filter_expression`
    tags_logical_operator: Annotated[
        LogicalExpression, Field(q=None, description="The logical operation to use when querying for tags")
    ] = LogicalExpression.AND

    updated_at: Annotated[
        datetime | None,
        Field(
            alias="updated_since",
            q="updated_at__gte",
            description="Find clusters that were updated after this datetime in ISO 8601 or "
            "Unix timestamps; ex: 2025-04-02T12:40:01-05:00",
        ),
    ] = None

    def get_filter_expression(self) -> Q:
        """Overrides parent method to remove the "tags_logical_operator" from the resulting
        filter expression because it is a meta filter
        """
        exp = super().get_filter_expression()
        for i, q in enumerate(exp.children):
            if isinstance(q, tuple) and q[0] == "tags_logical_operator":
                del exp.children[i]
                break
        return exp

    @pydantic.field_validator("tags")
    def validate_tags(cls, v: Any) -> list[str]:
        if v:
            return v.split(",")
        return v

    def filter_tags(self, value: list[str]) -> Q:
        """

        Args:
            value:

        Returns:

        """
        q = Q()

        if not value:
            return q

        for tag in value:
            if self.tags_logical_operator == LogicalExpression.AND:
                q &= Q(tags__name=tag)
            else:
                q |= Q(tags__name=tag)
        return q
