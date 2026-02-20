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
Tests for ChangeSet commit error handling in the Parameter Store API.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from api.tests.test_changesets import setup_user_with_permission
from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterIntent,
    CustomDataField,
    Group,
    GroupData,
)

User = get_user_model()


def create_intent(cluster, unique_zone_id, is_live=False, changeset=None):
    return ClusterIntent.objects.create(
        cluster=cluster,
        unique_zone_id=unique_zone_id,
        location="us-central1",
        machine_project_id="proj-1",
        fleet_project_id="proj-1",
        secrets_project_id="proj-1",
        cluster_ipv4_cidr="10.0.0.0/24",
        services_ipv4_cidr="10.0.1.0/24",
        external_load_balancer_ipv4_address_pools="10.0.2.0/24",
        sync_repo="http://git.repo",
        git_token_secrets_manager_name="token",
        cluster_version="1.0.0",
        is_live=is_live,
        changeset_id=changeset,
    )


def setup_intent_conflict_with_live(user):
    """
    Scenario:
    1. Live Cluster A has Intent Z1.
    2. ChangeSet has New Draft Cluster B with Intent Z1.
    Commit -> Conflict on Z1.
    """
    # Live
    g = Group.objects.create(name="G-Live", is_live=True)
    c = Cluster.objects.create(name="C-Live", group=g, is_live=True)
    create_intent(c, "Z1", is_live=True)

    # Draft
    cs = ChangeSet.objects.create(name="CS", created_by=user)
    c_draft = Cluster.objects.create(name="C-Draft", group=g, changeset_id=cs, is_live=False)
    create_intent(c_draft, "Z1", is_live=False, changeset=cs)

    return cs, "unique_zone_id", "violates the unique constraint"


def setup_group_data_conflict_with_live(user):
    """
    Scenario:
    1. Live Group G1 has GroupData (field F1).
    2. ChangeSet has New Draft GroupData (field F1) for the SAME Group G1.
    Commit -> Conflict on (Group, Field).
    """
    g = Group.objects.create(name="G1", is_live=True)
    field = CustomDataField.objects.create(name="F1")
    GroupData.objects.create(group=g, field=field, value="V1", is_live=True)

    cs = ChangeSet.objects.create(name="CS", created_by=user)
    GroupData.objects.create(group=g, field=field, value="V2", is_live=False, changeset_id=cs)

    return cs, "field", "violates the unique constraint"


def setup_cluster_data_conflict_with_live(user):
    """
    Scenario:
    1. Live Cluster C1 has ClusterData (field F1).
    2. ChangeSet has New Draft ClusterData (field F1) for the SAME Cluster C1.
    Commit -> Conflict on (Cluster, Field).
    """
    g = Group.objects.create(name="G1", is_live=True)
    c = Cluster.objects.create(name="C1", group=g, is_live=True)
    field = CustomDataField.objects.create(name="F1")
    ClusterData.objects.create(cluster=c, field=field, value="V1", is_live=True)

    cs = ChangeSet.objects.create(name="CS", created_by=user)
    ClusterData.objects.create(cluster=c, field=field, value="V2", is_live=False, changeset_id=cs)

    return cs, "field", "violates the unique constraint"


def setup_group_name_conflict_with_live(user):
    """
    Scenario:
    1. Live Group A has Name "G1".
    2. ChangeSet has New Draft Group B with Name "G1".
    Commit -> Conflict on Name "G1".
    """
    # Live
    Group.objects.create(name="G1", is_live=True)

    # Draft
    cs = ChangeSet.objects.create(name="CS", created_by=user)
    Group.objects.create(name="G1", changeset_id=cs, is_live=False)

    return cs, "name", "violates the unique constraint"


def setup_intra_cs_intent_conflict(user):
    """
    Scenario:
    1. ChangeSet has New Draft Cluster A with Intent Z1.
    2. ChangeSet has New Draft Cluster B with Intent Z1.
    Commit -> First one succeeds, second one fails with Conflict on Z1.
    """
    g = Group.objects.create(name="G-Live", is_live=True)
    cs = ChangeSet.objects.create(name="CS", created_by=user)

    # Draft 1
    c1 = Cluster.objects.create(name="C1", group=g, changeset_id=cs, is_live=False)
    create_intent(c1, "Z1", is_live=False, changeset=cs)

    # Draft 2
    c2 = Cluster.objects.create(name="C2", group=g, changeset_id=cs, is_live=False)
    create_intent(c2, "Z1", is_live=False, changeset=cs)

    return cs, "unique_zone_id", "violates the unique constraint"


def setup_intra_cs_group_name_conflict(user):
    """
    Scenario:
    1. ChangeSet has New Draft Group A with Name "G1".
    2. ChangeSet has New Draft Group B with Name "G1".
    Commit -> First one succeeds, second one fails with Conflict on G1.
    """
    cs = ChangeSet.objects.create(name="CS", created_by=user)

    Group.objects.create(name="G1", changeset_id=cs, is_live=False)
    Group.objects.create(name="G1", changeset_id=cs, is_live=False)

    return cs, "name", "violates the unique constraint"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup_func",
    [
        setup_intent_conflict_with_live,
        setup_group_name_conflict_with_live,
        setup_intra_cs_group_name_conflict,
        setup_group_data_conflict_with_live,
        setup_cluster_data_conflict_with_live,
    ],
)
def test_commit_changeset_errors(setup_func):
    """
    Parametrized test to verify various Commit-time database integrity errors.
    """
    user = setup_user_with_permission("api.params_api_update_changeset")

    cs, error_field, error_msg_part = setup_func(user)

    client = Client()
    client.force_login(user)

    response = client.post(f"/api/v1/changeset/{cs.id}/commit")

    assert response.status_code == 422
    data = response.json()

    # Check that we have a key that looks like "Entity 'Name' (field)"
    # e.g., "Cluster 'C-Draft' (unique_zone_id)"
    found_key = False
    for key, messages in data["message"].items():
        if f"({error_field})" in key:
            found_key = True
            assert any(error_msg_part in msg for msg in messages), f"Expected '{error_msg_part}' in {messages}"
            break

    assert found_key, f"Could not find error for field '{error_field}' in {data['message'].keys()}"
