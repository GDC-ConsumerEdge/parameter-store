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
Main Entry point for the Parameter Store API v1.

This module initializes the NinjaAPI instance and registers the routers for
Clusters, Groups, and ChangeSets.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpRequest
from ninja import NinjaAPI
from ninja.pagination import LimitOffsetPagination
from ninja.pagination import paginate as ninja_paginate
from ninja.responses import codes_4xx
from ninja.security import django_auth

from parameter_store.models import CustomDataField, Tag

from .api_changesets import changesets_router
from .api_clusters import clusters_router
from .api_groups import groups_router
from .exc import validation_errors
from .schema.request import (
    CustomDataFieldCreateRequest,
    CustomDataFieldUpdateRequest,
    TagCreateRequest,
    TagUpdateRequest,
)
from .schema.response import (
    HealthResponse,
    MessageResponse,
    NameDescResponse,
    PingResponse,
)
from .utils import require_permissions

api_v1 = NinjaAPI(title="Parameter Store API", version="1.1.0", docs_decorator=staff_member_required, auth=django_auth)

api_v1.add_router("", changesets_router)
api_v1.add_router("", groups_router)
api_v1.add_router("", clusters_router)

api_v1.exception_handler(ValidationError)(validation_errors)


@api_v1.get("/ping", response=PingResponse, summary="Basic health check", tags=["General"])
def ping(request: HttpRequest):
    """
    A lightweight connectivity check to verify the API service is reachable and the Django server is running.
    """
    return {"status": "ok"}


@api_v1.get("/status", response=HealthResponse, summary="Deep health check with database status", tags=["General"])
@api_v1.get("/healthz", response=HealthResponse, summary="Deep health check with database status", tags=["General"])
def health(request: HttpRequest):
    """
    A comprehensive health check that verifies database connectivity and ensures all migrations have been applied.
    """
    health_status = {
        "status": "ok",
        "database": {
            "status": "ok",
            "details": {
                "connections": {},
                "migrations": "ok",
            },
            "errors": [],
        },
    }

    # Check database connections
    for db_name in connections.databases:
        try:
            db_conn = connections[db_name]
            db_conn.ensure_connection()
            health_status["database"]["details"]["connections"][db_name] = {
                "status": "ok",
                "backend": db_conn.vendor,
            }
        except Exception as e:
            health_status["status"] = "error"
            health_status["database"]["status"] = "error"
            health_status["database"]["details"]["connections"][db_name] = {"status": "error", "error": str(e)}
            health_status["database"]["errors"].append(f"Connection error ({db_name}): {str(e)}")

    # Check migrations
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            health_status["database"]["details"]["migrations"] = "pending"
            health_status["status"] = "degraded"
            health_status["database"]["errors"].append(f"Pending migrations: {len(plan)}")
    except Exception as e:
        health_status["database"]["details"]["migrations"] = "error"
        health_status["status"] = "error"
        health_status["database"]["errors"].append(f"Migration check error: {str(e)}")

    return health_status


@api_v1.get(
    "/tags",
    response={200: list[NameDescResponse], codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get cluster tags",
    tags=["Tags"],
)
@ninja_paginate(LimitOffsetPagination)
@require_permissions("api.params_api_read_tag", "api.params_api_read_objects")
def tags(request):
    """
    Returns a list of all unique tags that have been defined in the system for use with clusters.
    """
    return Tag.objects.all()


@api_v1.post(
    "/tags",
    response={200: NameDescResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new cluster tag",
    tags=["Tags"],
)
@require_permissions("api.params_api_create_tag", "api.params_api_create_objects")
def create_tag(request: HttpRequest, payload: TagCreateRequest):
    """
    Creates a new tag that can be applied to clusters.
    """
    if Tag.objects.filter(name=payload.name).exists():
        return 409, {"message": f"Tag '{payload.name}' already exists."}

    tag = Tag.objects.create(name=payload.name, description=payload.description)
    return 200, tag


@api_v1.put(
    "/tags/{tag_name}",
    response={200: NameDescResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a cluster tag",
    tags=["Tags"],
)
@require_permissions("api.params_api_update_tag", "api.params_api_update_objects")
def update_tag(request: HttpRequest, tag_name: str, payload: TagUpdateRequest):
    """
    Updates the description of an existing tag.
    """
    try:
        tag = Tag.objects.get(name=tag_name)
    except Tag.DoesNotExist:
        return 404, {"message": f"Tag '{tag_name}' not found."}

    if payload.description is not None:
        tag.description = payload.description
        tag.save(update_fields=["description", "updated_at"])

    return 200, tag


@api_v1.get(
    "/data-fields",
    response={200: list[NameDescResponse], codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get data fields",
    tags=["Data Fields"],
)
@ninja_paginate(LimitOffsetPagination)
@require_permissions("api.params_api_read_customdatafield", "api.params_api_read_objects")
def custom_data_fields(request):
    """
    Returns a list of all data fields that have been defined in the system.
    """
    return CustomDataField.objects.all()


@api_v1.post(
    "/data-fields",
    response={200: NameDescResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Create a new data field",
    tags=["Data Fields"],
)
@require_permissions("api.params_api_create_customdatafield", "api.params_api_create_objects")
def create_custom_data_field(request: HttpRequest, payload: CustomDataFieldCreateRequest):
    """
    Creates a new data field.
    """
    if CustomDataField.objects.filter(name=payload.name).exists():
        return 409, {"message": f"Data field '{payload.name}' already exists."}

    field = CustomDataField.objects.create(name=payload.name, description=payload.description)
    return 200, field


@api_v1.put(
    "/data-fields/{field_name}",
    response={200: NameDescResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Update a data field",
    tags=["Data Fields"],
)
@require_permissions("api.params_api_update_customdatafield", "api.params_api_update_objects")
def update_custom_data_field(request: HttpRequest, field_name: str, payload: CustomDataFieldUpdateRequest):
    """
    Updates the name or description of an existing data field.
    """
    try:
        field = CustomDataField.objects.get(name=field_name)
    except CustomDataField.DoesNotExist:
        return 404, {"message": f"Data field '{field_name}' not found."}

    update_fields = ["updated_at"]
    if payload.name is not None and payload.name != field.name:
        if CustomDataField.objects.filter(name=payload.name).exists():
            return 409, {"message": f"Data field '{payload.name}' already exists."}
        field.name = payload.name
        update_fields.append("name")

    if payload.description is not None:
        field.description = payload.description
        update_fields.append("description")

    field.save(update_fields=update_fields)

    return 200, field
