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
End-to-end tests for successful ChangeSet commit promoting child entities.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from api.tests.test_changesets import setup_user_with_permission
from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    CustomDataField,
    Group,
    GroupData,
)

User = get_user_model()


@pytest.mark.django_db
def test_commit_promotes_all_child_entities_e2e():
    """
    E2E scenario:
    1. Create a ChangeSet.
    2. Create a Group draft with GroupData.
    3. Create a Cluster draft with ClusterIntent, ClusterFleetLabel, and ClusterData.
    4. Link them.
    5. Commit via API.
    6. Verify everything is live.
    """
    user = setup_user_with_permission("api.params_api_update_changeset")
    client = Client()
    client.force_login(user)

    cs = ChangeSet.objects.create(name="E2E Happy Path", created_by=user)

    # 1. Group Draft
    group_draft = Group.objects.create(name="E2E-G1", is_live=False, changeset_id=cs)
    field_g = CustomDataField.objects.create(name="g-field")
    GroupData.objects.create(group=group_draft, field=field_g, value="gv1", is_live=False, changeset_id=cs)

    # 2. Cluster Draft
    cluster_draft = Cluster.objects.create(name="E2E-C1", group=group_draft, is_live=False, changeset_id=cs)

    # ClusterIntent
    ClusterIntent.objects.create(
        cluster=cluster_draft,
        unique_zone_id="E2E-Z1",
        location="us-central1",
        machine_project_id="p1",
        fleet_project_id="p1",
        secrets_project_id="p1",
        cluster_ipv4_cidr="10.0.0.0/24",
        services_ipv4_cidr="10.0.1.0/24",
        external_load_balancer_ipv4_address_pools="10.0.2.0/24",
        sync_repo="http://git",
        git_token_secrets_manager_name="t",
        cluster_version="1.0",
        is_live=False,
        changeset_id=cs,
    )

    # ClusterFleetLabel
    ClusterFleetLabel.objects.create(cluster=cluster_draft, key="k1", value="v1", is_live=False, changeset_id=cs)

    # ClusterData
    field_c = CustomDataField.objects.create(name="c-field")
    ClusterData.objects.create(cluster=cluster_draft, field=field_c, value="cv1", is_live=False, changeset_id=cs)

    # 3. Commit via API
    response = client.post(f"/api/v1/changeset/{cs.id}/commit")
    assert response.status_code == 200

    # 4. Verify Live State
    assert Group.objects.filter(name="E2E-G1", is_live=True).exists()
    group_live = Group.objects.get(name="E2E-G1", is_live=True)
    assert GroupData.objects.filter(group=group_live, field=field_g, value="gv1", is_live=True).exists()

    assert Cluster.objects.filter(name="E2E-C1", is_live=True).exists()
    cluster_live = Cluster.objects.get(name="E2E-C1", is_live=True)
    assert cluster_live.group == group_live

    assert ClusterIntent.objects.filter(cluster=cluster_live, unique_zone_id="E2E-Z1", is_live=True).exists()
    assert ClusterFleetLabel.objects.filter(cluster=cluster_live, key="k1", value="v1", is_live=True).exists()
    assert ClusterData.objects.filter(cluster=cluster_live, field=field_c, value="cv1", is_live=True).exists()

    # Verify ChangeSet status
    cs.refresh_from_db()
    assert cs.status == ChangeSet.Status.COMMITTED
