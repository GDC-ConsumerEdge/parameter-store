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

from parameter_store.models import Tag

from .api_changesets import changesets_router
from .api_clusters import clusters_router
from .api_groups import groups_router
from .exc import validation_errors
from .schema.response import (
    HealthResponse,
    MessageResponse,
    NameDescResponse,
    PingResponse,
)
from .utils import require_permissions

api_v1 = NinjaAPI(title="Parameter Store API", version="1.0.0", docs_decorator=staff_member_required, auth=django_auth)

api_v1.add_router("", changesets_router)
api_v1.add_router("", groups_router)
api_v1.add_router("", clusters_router)

api_v1.exception_handler(ValidationError)(validation_errors)


@api_v1.get("/ping", response=PingResponse, summary="Basic health check")
def ping(request: HttpRequest):
    """This health check is very basic, providing only a basic alive check of the API
    application and Django server.  No database checks are performed.  If you receive an HTTP 200
    status with a response body, the server is alive.
    """
    return {"status": "ok"}


@api_v1.get("/status", response=HealthResponse, summary="Deep health check with database status")
@api_v1.get("/healthz", response=HealthResponse, summary="Deep health check with database status")
def health(request: HttpRequest):
    """Health check endpoint that verifies database connectivity and migrations status."""
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
)
@ninja_paginate(LimitOffsetPagination)
@require_permissions("api.params_api_read_tag", "api.params_api_read_objects")
def tags(request):
    """Clusters may have tags associated with them. Tags are simple string values. This endpoint
    returns all available tags which may be associated with a cluster.
    """
    return Tag.objects.all()
