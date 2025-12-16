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
from ninja import NinjaAPI, Query
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination
from ninja.pagination import paginate as ninja_paginate
from ninja.responses import codes_4xx, codes_5xx
from ninja.security import django_auth

from parameter_store.models import Cluster, Tag

from .api_changesets import changesets_router
from .api_groups import groups_router
from .exc import validation_errors
from .schema.filters import ClusterFilter
from .schema.response import (
    ClusterResponse,
    ClustersResponse,
    FleetLabelResponse,
    HealthResponse,
    MessageResponse,
    NameDescResponse,
    PingResponse,
)
from .utils import paginate, require_permissions

api_v1 = NinjaAPI(title="Parameter Store API", version="1.0.0", docs_decorator=staff_member_required, auth=django_auth)

api_v1.add_router("", changesets_router)
api_v1.add_router("", groups_router)


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


def _generate_cluster_response(cluster: Cluster) -> ClusterResponse:
    return ClusterResponse(
        name=cluster.name,
        description=cluster.description,
        group=cluster.group.name,
        secondary_groups=[g.name for g in cluster.secondary_groups.all()],
        tags=[tag.name for tag in cluster.tags.all()],
        fleet_labels=[FleetLabelResponse(key=fl.key, value=fl.value) for fl in cluster.fleet_labels.all()],
        intent=cluster.intent if hasattr(cluster, "intent") else None,
        data={d.field.name: d.value for d in cluster.cluster_data.all()} if cluster.cluster_data.exists() else None,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
    )


@api_v1.get(
    "/cluster/{cluster}",
    response={200: ClusterResponse, codes_4xx: MessageResponse, codes_5xx: MessageResponse},
    auth=django_auth,
    summary="Get a single cluster",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_cluster(request: HttpRequest, cluster: str):
    """This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    try:
        c = Cluster.objects.with_related().get(name=cluster)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}
    except Cluster.MultipleObjectsReturned:
        raise HttpError(500, "multiple clusters found")

    return _generate_cluster_response(c)


@api_v1.get(
    "/clusters",
    response={200: ClustersResponse, codes_4xx: MessageResponse},
    auth=django_auth,
    summary="Get many clusters",
)
@require_permissions("api.params_api_read_cluster", "api.params_api_read_objects")
def get_clusters(request: HttpRequest, filters: Query[ClusterFilter], limit=250, offset=0):
    """This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    qs = Cluster.objects.filter(is_live=True).with_related()
    clusters = paginate(filters.filter(qs), limit, offset)

    out = (_generate_cluster_response(cluster) for cluster in clusters)
    return {"clusters": out, "count": clusters.count()}
