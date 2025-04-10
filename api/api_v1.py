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
from django.db.models import Prefetch
from django.http import HttpRequest
from ninja import NinjaAPI, Query
from ninja.errors import HttpError
from ninja.pagination import LimitOffsetPagination
from ninja.pagination import paginate as ninja_paginate
from ninja.security import django_auth

from parameter_store.models import Cluster, Group, Tag, GroupData
from .schema.filters import ClusterFilter
from .schema.out import HealthResponse, NameDescResponse, ClustersResponse, \
    ClusterResponse, FleetLabelResponse, PingResponse, GroupResponse, MessageResponse, \
    GroupsResponse
from .utils import require_permissions, paginate

api_v1 = NinjaAPI(title="Parameter Store API",
                  version='1.0.0',
                  csrf=True,
                  docs_decorator=staff_member_required)


@api_v1.get('/ping', response=PingResponse, summary='Basic health check')
def ping(request: HttpRequest):
    """ This health check is very basic, providing only a basic alive check of the API
    application and Django server.  No database checks are performed.  If you receive an HTTP 200
    status with a response body, the server is alive.
    """
    return {'status': 'ok'}


@api_v1.get(
    "/status",
    response=HealthResponse,
    summary="Deep health check with database status")
def health(request: HttpRequest):
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
    summary='Get cluster tags')
@ninja_paginate(LimitOffsetPagination)
@require_permissions('can_get_params_api')
def tags(request):
    """ Clusters may have tags associated with them. Tags are simple string values. This endpoint
    returns all available tags which may be associated with a cluster.
    """
    return Tag.objects.all()


@api_v1.get(
    '/group/{group}',
    response={200: GroupResponse, 404: MessageResponse, 409: MessageResponse},
    auth=django_auth,
    summary='Get a single group')
def get_group(request: HttpRequest, group: str):
    """   Gets a specific group by its name.
    """
    # Query the for the group, prefetch related data
    groups = Group.objects.prefetch_related(
        Prefetch('group_data', queryset=GroupData.objects.select_related('field')))

    try:
        g = groups.get(name=group)
    except Group.DoesNotExist:
        return 404, {"message": "group not found"}
    except Group.MultipleObjectsReturned:
        raise HttpError(500, "multiple groups found")

    return GroupResponse(
        name=g.name,
        description=g.description,
        data={d.field.name: d.value for d in
              g.group_data.all()} if g.group_data.exists() else None,
    )


@api_v1.get(
    "/groups",
    response=GroupsResponse,
    auth=django_auth,
    summary='Get many groups')
@require_permissions('can_get_params_api')
def get_groups(request: HttpRequest, limit=250, offset=0):
    """ Clusters belong to groups. This endpoint returns all available groups to which a cluster
    may belong.
    """
    # Query the for the groups while prefetching related data
    data_prefetch = Prefetch('group_data', queryset=GroupData.objects.select_related('field'))
    qs = Group.objects.prefetch_related(data_prefetch).all()
    groups = paginate(qs, limit, offset)

    out = (
        GroupResponse(
            name=group.name,
            description=group.description,
            data={d.field.name: d.value for d in
                  group.group_data.all()} if group.group_data.exists() else None,
        ) for group in groups
    )
    return {'groups': out, 'count': groups.count()}


@api_v1.get(
    '/cluster/{cluster}',
    response={200: ClusterResponse, 404: MessageResponse, 500: MessageResponse},
    auth=django_auth,
    summary='Get a single cluster')
@require_permissions('can_get_params_api')
def get_cluster(request: HttpRequest, cluster: str):
    """ This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    try:
        c = Cluster.objects.with_related().get(name=cluster)
    except Cluster.DoesNotExist:
        return 404, {"message": "cluster not found"}
    except Cluster.MultipleObjectsReturned:
        raise HttpError(500, "multiple clusters found")

    return ClusterResponse(
        name=c.name,
        description=c.description,
        group=c.group.name,
        secondary_groups=[g.name for g in c.secondary_groups.all()],
        tags=[tag.name for tag in c.tags.all()],
        fleet_labels=[
            FleetLabelResponse(key=fl.key, value=fl.value)
            for fl in c.fleet_labels.all()
        ],
        intent=c.intent if hasattr(c, 'intent') else None,
        data={
            d.field.name: d.value
            for d in c.cluster_data.all()
        } if c.cluster_data.exists() else None,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@api_v1.get(
    '/clusters',
    response=ClustersResponse,
    auth=django_auth,
    summary='Get many clusters')
@require_permissions('can_get_params_api')
def get_clusters(request: HttpRequest, filters: Query[ClusterFilter], limit=250, offset=0):
    """ This API endpoint provides view-only cluster objects and their associated metadata,
    including cluster group, fleet label, custom data, cluster intent.
    """
    clusters = paginate(filters.filter(Cluster.objects.with_related()), limit, offset)

    out = (
        ClusterResponse(
            name=cluster.name,
            description=cluster.description,
            group=cluster.group.name,
            secondary_groups=[g.name for g in cluster.secondary_groups.all()],
            tags=[tag.name for tag in cluster.tags.all()],
            fleet_labels=[
                FleetLabelResponse(key=fl.key, value=fl.value)
                for fl in cluster.fleet_labels.all()
            ],
            intent=cluster.intent if hasattr(cluster, 'intent') else None,
            data={
                d.field.name: d.value
                for d in cluster.cluster_data.all()
            } if cluster.cluster_data.exists() else None,
            created_at=cluster.created_at,
            updated_at=cluster.updated_at,
        ) for cluster in clusters
    )
    return {'clusters': out, 'count': clusters.count()}
