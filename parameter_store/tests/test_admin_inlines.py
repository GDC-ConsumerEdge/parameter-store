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

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.urls import reverse

from parameter_store.admin_inlines import ClusterDataInline
from parameter_store.models import ChangeSet, Cluster, ClusterData, CustomDataField, Group

pytestmark = pytest.mark.django_db


@pytest.fixture
def user() -> User:
    return User.objects.create_superuser("admin", "admin@example.com", "password")


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


def test_changeset_aware_inline_mixin_get_queryset(rf, user):
    """
    Tests that ChangeSetAwareInlineMixin filters queryset correctly
    based on the parent object's live status.
    """
    changeset = ChangeSet.objects.create(name="CS", created_by=user)
    group = Group.objects.create(name="Group", is_live=True)
    live_cluster = Cluster.objects.create(name="Live Cluster", group=group, is_live=True)
    draft_cluster = Cluster.objects.create(name="Draft Cluster", group=group, is_live=False, changeset_id=changeset)

    field = CustomDataField.objects.create(name="field")

    live_data = ClusterData.objects.create(cluster=live_cluster, field=field, value="live", is_live=True)
    draft_data = ClusterData.objects.create(
        cluster=draft_cluster, field=field, value="draft", is_live=False, changeset_id=changeset
    )

    inline = ClusterDataInline(Cluster, admin.AdminSite())

    # Mock request for live cluster
    url = reverse("param_admin:parameter_store_cluster_change", args=[live_cluster.pk])
    request = rf.get(url)

    qs = inline.get_queryset(request)
    assert qs.count() == 1
    assert qs.first() == live_data

    # Mock request for draft cluster
    url = reverse("param_admin:parameter_store_cluster_change", args=[draft_cluster.pk])
    request = rf.get(url)

    qs = inline.get_queryset(request)
    assert qs.count() == 1
    assert qs.first() == draft_data
