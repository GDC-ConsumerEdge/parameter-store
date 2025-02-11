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
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from ninja import NinjaAPI, Query
from ninja.pagination import LimitOffsetPagination
from ninja.pagination import paginate as ninja_paginate
from ninja.responses import codes_4xx, codes_5xx
from ninja.security import django_auth

from parameter_store.models import Cluster, Group, Tag
from .schema.filters import ClusterFilter
from .schema.out import HealthResponse, MessageResponse, NameDescResponse, ClustersResponse, \
    ClusterResponse, FleetLabelResponse, PingResponse
from .utils import require_permissions, paginate

api_v1 = NinjaAPI(title="Parameter Store API",
                  version='1.0.0',
                  csrf=True,
                  docs_decorator=staff_member_required)

std_resp = {codes_4xx: MessageResponse,
            codes_5xx: MessageResponse}


@api_v1.get('/ping', response=PingResponse, summary='Basic health check')
def ping(request):
    """ This health check is very basic, providing only a basic alive check of the API
    application and Django server.  No database checks are performed.  If you receive an HTTP 200
    status with a response body, the server is alive.
    """
    return {'status': 'ok'}


@api_v1.get(
    "/status",
    response=HealthResponse,
    summary="Deep health check with database status")
def health(request):
    """  Health check endpoint that verifies database connectivity and migrations status.
    """
    health_status = {
        'status': 'ok',
        'database': {
            'status': 'ok',
            'details': {
                'connections': {},
                'migrations': 'ok',
            },
            'errors': []
        }
    }

    # Check database connections
    for db_name in connections.databases:
        try:
            db_conn = connections[db_name]
            db_conn.ensure_connection()
            health_status['database']['details']['connections'][db_name] = {
                'status': 'ok',
                'backend': db_conn.vendor,
            }
        except Exception as e:
            health_status['status'] = 'error'
            health_status['database']['status'] = 'error'
            health_status['database']['details']['connections'][db_name] = {
                'status': 'error',
                'error': str(e)
            }
            health_status['database']['errors'].append(f"Connection error ({db_name}): {str(e)}")

    # Check migrations
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            health_status['database']['details']['migrations'] = 'pending'
            health_status['status'] = 'degraded'
            health_status['database']['errors'].append(
                f"Pending migrations: {len(plan)}"
            )
    except Exception as e:
        health_status['database']['details']['migrations'] = 'error'
        health_status['status'] = 'error'
        health_status['database']['errors'].append(f"Migration check error: {str(e)}")

    return health_status


@api_v1.get(
    '/tags',
    response=list[NameDescResponse],
    auth=django_auth,
    summary='Cluster tags')
@ninja_paginate(LimitOffsetPagination)
@require_permissions('can_get_params_api')
def tags(request):
    """ Clusters may have tags associated with them. Tags are simple string values.  This endpoint returns
    all avaialbe tags which may be associated with a cluster.
    """
    return Tag.objects.all()


@api_v1.get(
    "/groups",
    response=list[NameDescResponse],
    auth=django_auth,
    summary='Groups')
@ninja_paginate(LimitOffsetPagination)
@require_permissions('can_get_params_api')
def groups(request):
    """ Clusters belong to groups. This endpoint returns all available groups to which a cluster
    may belong.
    """
    return Group.objects.all()


@api_v1.get(
    '/clusters',
    response=ClustersResponse,
    auth=django_auth,
    summary='Clusters and their associated data')
@require_permissions('can_get_params_api')
def get_clusters(request, filters: Query[ClusterFilter], limit=250, offset=0):
    """ This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    clusters = paginate(filters.filter(Cluster.objects.with_related()), limit, offset)

    out = [
        ClusterResponse(
            name=cluster.name,
            description=cluster.description,
            group=cluster.group.name,
            tags=[tag.name for tag in cluster.tags.all()],
            fleet_labels=[
                FleetLabelResponse(key=fl.key, value=fl.value)
                for fl in cluster.fleet_labels.all()
            ],
            intent=cluster.intent if hasattr(cluster, 'intent') else None,
            data={
                d.field.name: d.value
                for d in cluster.data.all()
            } if cluster.data.exists() else None,
        ) for cluster in clusters
    ]
    return {'clusters': out, 'count': clusters.count()}
