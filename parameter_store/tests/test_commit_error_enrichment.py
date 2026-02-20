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
Tests for error enrichment in ChangeSet.commit via the inner _save_with_context.
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    CustomDataField,
    Group,
    GroupData,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    """Provides a superuser for authentication in tests."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def changeset(user: User) -> ChangeSet:
    """Provides a draft ChangeSet for testing commits."""
    return ChangeSet.objects.create(name="Test CS", created_by=user)


def create_intent(cluster, unique_zone_id, is_live=False, changeset=None):
    from parameter_store.models import ClusterIntent

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


def test_commit_group_error_enrichment(changeset: ChangeSet, user: User) -> None:
    """Verifies that a Group name conflict during commit yields an enriched error key."""
    # Create a live group.
    Group.objects.create(name="LiveGroup", is_live=True)

    # Create a draft group with the same name in a changeset.
    Group.objects.create(name="LiveGroup", is_live=False, changeset_id=changeset)

    with pytest.raises(ValidationError) as excinfo:
        changeset.commit(user)

    # Expected key format: "Group 'LiveGroup' (name)"
    assert "Group 'LiveGroup' (name)" in excinfo.value.message_dict


def test_commit_cluster_error_enrichment(changeset: ChangeSet, user: User) -> None:
    """Verifies that a Cluster-related error (via ClusterIntent) yields an enriched error key."""
    group = Group.objects.create(name="Group", is_live=True)

    # Live cluster C1 with zone Z1
    c1 = Cluster.objects.create(name="C1", group=group, is_live=True)
    create_intent(c1, "Z1", is_live=True)

    # Draft cluster C2 with SAME zone Z1
    c2 = Cluster.objects.create(name="C2", group=group, is_live=False, changeset_id=changeset)
    create_intent(c2, "Z1", is_live=False, changeset=changeset)

    with pytest.raises(ValidationError) as excinfo:
        changeset.commit(user)

    # ClusterIntent has root = entity.cluster
    assert "Cluster 'C2' (unique_zone_id)" in excinfo.value.message_dict


def test_commit_group_data_error_enrichment(changeset: ChangeSet, user: User) -> None:
    """Verifies that a GroupData conflict during commit yields an error key referencing the Group."""
    group = Group.objects.create(name="G-DataTest", is_live=True)
    field = CustomDataField.objects.create(name="env-unique")

    # Live group data.
    GroupData.objects.create(group=group, field=field, value="prod", is_live=True)

    # Draft group data for the same group and field.
    other_cs = ChangeSet.objects.create(name="Other CS", created_by=user)
    GroupData.objects.create(group=group, field=field, value="stg", is_live=False, changeset_id=other_cs)

    with pytest.raises(ValidationError) as excinfo:
        other_cs.commit(user)

    # Expected key format: "Group 'G-DataTest' (field)"
    assert "Group 'G-DataTest' (field)" in excinfo.value.message_dict


def test_commit_cluster_data_error_enrichment(changeset: ChangeSet, user: User) -> None:
    """Verifies that a ClusterData conflict during commit yields an error key referencing the Cluster."""
    group = Group.objects.create(name="G-DataTest", is_live=True)
    cluster = Cluster.objects.create(name="C-DataTest", group=group, is_live=True)
    field = CustomDataField.objects.create(name="env-cluster")

    # Live cluster data.
    ClusterData.objects.create(cluster=cluster, field=field, value="prod", is_live=True)

    # Draft cluster data for the same cluster and field.
    other_cs = ChangeSet.objects.create(name="Other CS ClusterData", created_by=user)
    ClusterData.objects.create(cluster=cluster, field=field, value="stg", is_live=False, changeset_id=other_cs)

    with pytest.raises(ValidationError) as excinfo:
        other_cs.commit(user)

    # Expected key format: "Cluster 'C-DataTest' (field)"
    assert "Cluster 'C-DataTest' (field)" in excinfo.value.message_dict


def test_commit_fleet_label_error_enrichment(changeset: ChangeSet, user: User) -> None:
    """Verifies that a ClusterFleetLabel conflict during commit yields an error key referencing the Cluster."""
    from parameter_store.models import ClusterFleetLabel

    group = Group.objects.create(name="G-LabelTest", is_live=True)
    cluster = Cluster.objects.create(name="C-LabelTest", group=group, is_live=True)

    # Live label.
    ClusterFleetLabel.objects.create(cluster=cluster, key="tier", value="gold", is_live=True)

    # Draft label.
    other_cs = ChangeSet.objects.create(name="Other CS Label", created_by=user)
    ClusterFleetLabel.objects.create(cluster=cluster, key="tier", value="silver", is_live=False, changeset_id=other_cs)

    with pytest.raises(ValidationError) as excinfo:
        other_cs.commit(user)

    # Expected key format: "Cluster 'C-LabelTest' (key)"
    assert "Cluster 'C-LabelTest' (key)" in excinfo.value.message_dict
