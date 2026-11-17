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
Tests for the Django Admin interception logic.

This module contains functional tests verifying that the ChangeSetAwareAdminMixin
correctly intercepts deletion requests to stage them as ChangeSet drafts.
"""

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from parameter_store.admin_mixins import ChangeSetAwareAdminMixin
from parameter_store.models import ChangeSet, Group

# Mark all tests in this file as requiring database access
pytestmark = pytest.mark.django_db

User = get_user_model()


class MockGroupAdmin(ChangeSetAwareAdminMixin, admin.ModelAdmin):
    """Mock Admin class for testing mixin behavior."""

    pass


@pytest.fixture
def admin_site():
    """Fixture providing a Django AdminSite."""
    return AdminSite()


@pytest.fixture
def group_admin(admin_site):
    """Fixture providing a MockGroupAdmin instance."""
    return MockGroupAdmin(Group, admin_site)


@pytest.fixture
def rf():
    """Fixture providing a RequestFactory."""
    return RequestFactory()


@pytest.fixture
def user():
    """Fixture providing a superuser."""
    return User.objects.create_superuser("admin", "admin@example.com", "password")


def test_delete_view_intercepts_live_object(group_admin, rf, user):
    """
    Test that delete_view intercepts POST requests for live objects.

    Verifies that deleting a live object stages it for deletion in the active
    ChangeSet rather than deleting it immediately.
    """
    # Setup
    changeset = ChangeSet.objects.create(name="Test ChangeSet", created_by=user)
    group = Group.objects.create(name="Live Group", is_live=True)

    # Request
    request = rf.post(reverse("admin:parameter_store_group_delete", args=[group.pk]))
    request.user = user
    request.session = {"active_changeset_id": changeset.id}
    setattr(request, "_messages", FallbackStorage(request))

    # Execute
    response = group_admin.delete_view(request, str(group.pk))

    # Assertions
    assert response.status_code == 302
    assert response.url == reverse("param_admin:parameter_store_group_changelist")

    group.refresh_from_db()
    assert group.is_locked is True
    assert group.locked_by_changeset == changeset

    draft = Group.objects.get(draft_of=group, changeset_id=changeset)
    assert draft.is_pending_deletion is True

    # Check messages
    messages = [m.message for m in request._messages]
    assert any("staged for deletion" in m for m in messages)
    # Ensure standard "deleted successfully" message is NOT present
    assert not any("deleted successfully" in m for m in messages)


def test_delete_view_allows_draft_deletion(group_admin, rf, user):
    """
    Test that delete_view allows standard deletion for draft objects.

    Verifies that draft objects (which are not live) can be deleted normally
    without being intercepted by the ChangeSet staging logic.
    """
    # Setup
    changeset = ChangeSet.objects.create(name="Test ChangeSet", created_by=user)
    draft = Group.objects.create(name="Draft Group", is_live=False, changeset_id=changeset)

    # Request
    request = rf.post(reverse("admin:parameter_store_group_delete", args=[draft.pk]), data={"post": "yes"})
    request.user = user
    request.session = {"active_changeset_id": changeset.id}
    request._dont_enforce_csrf_checks = True
    setattr(request, "_messages", FallbackStorage(request))

    # Execute
    response = group_admin.delete_view(request, str(draft.pk))

    # Assertions
    assert response.status_code == 302
    # Verify draft is actually deleted
    assert not Group.objects.filter(pk=draft.pk).exists()


def test_delete_view_denies_zero_permission_staff_user_on_post(group_admin: MockGroupAdmin, rf: RequestFactory) -> None:
    """Verifies that a zero-permission staff user is denied on POST to delete_view."""
    from django.contrib.auth.models import Permission
    from django.core.exceptions import PermissionDenied
    from django.test import Client

    from parameter_store.models import Cluster, ClusterData, CustomDataField

    admin_user = User.objects.create_superuser("super", "super@example.com", "password")
    admin_cs = ChangeSet.objects.create(name="Admin Draft CS", created_by=admin_user)
    live_group = Group.objects.create(name="Protected Live Group", is_live=True)
    live_cluster = Cluster.objects.create(name="Protected Live Cluster", group=live_group, is_live=True)

    attacker = User.objects.create_user("lowpriv", "lowpriv@example.com", "password", is_staff=True)
    assert list(attacker.get_all_permissions()) == []

    # Direct view call with attacker's session pointing at admin's ChangeSet
    request = rf.post(reverse("param_admin:parameter_store_group_delete", args=[live_group.pk]), data={"post": "yes"})
    request.user = attacker
    request.session = {"active_changeset_id": admin_cs.id}
    setattr(request, "_messages", FallbackStorage(request))

    with pytest.raises(PermissionDenied):
        group_admin.delete_view(request, str(live_group.pk))

    # Non-existent object_id also raises PermissionDenied without leaking existence
    with pytest.raises(PermissionDenied):
        group_admin.delete_view(request, "999999")

    # Full HTTP client verification across both GET and POST for Cluster and Group
    http_client = Client()
    http_client.force_login(attacker)

    for model_name, pk in [("cluster", live_cluster.pk), ("group", live_group.pk)]:
        delete_url = reverse(f"param_admin:parameter_store_{model_name}_delete", args=[pk])
        get_resp = http_client.get(delete_url)
        assert get_resp.status_code == 403

        post_resp = http_client.post(delete_url, data={"post": "yes"})
        assert post_resp.status_code == 403

    live_group.refresh_from_db()
    live_cluster.refresh_from_db()
    assert live_group.is_locked is False
    assert live_cluster.is_locked is False
    assert not Group.objects.filter(is_live=False).exists()
    assert not Cluster.objects.filter(is_live=False).exists()
    assert not ChangeSet.objects.filter(created_by=attacker).exists()

    # Verify CSRF enforcement rejects tokenless POST requests
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)
    csrf_resp = csrf_client.post(
        reverse("param_admin:parameter_store_cluster_delete", args=[live_cluster.pk]),
        data={"post": "yes"},
    )
    assert csrf_resp.status_code == 403

    # Verify Editor (view + change, no delete) cannot stage live deletion but CAN discard a draft
    editor = User.objects.create_user("editor", "editor@example.com", "password", is_staff=True)
    for codename in ["view_cluster", "add_cluster", "change_cluster", "view_group", "change_group"]:
        perm = Permission.objects.get(codename=codename, content_type__app_label="parameter_store")
        editor.user_permissions.add(perm)

    editor_client = Client()
    editor_client.force_login(editor)

    # Editor POST to live cluster delete_view -> 403 Forbidden
    live_del_url = reverse("param_admin:parameter_store_cluster_delete", args=[live_cluster.pk])
    assert editor_client.get(live_del_url).status_code == 403
    assert editor_client.post(live_del_url, data={"post": "yes"}).status_code == 403
    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is False

    # Editor creates a draft with child data, then discards that draft via delete_view
    editor_cs = ChangeSet.objects.create(name="Editor CS", created_by=editor)
    draft_cluster = live_cluster.create_draft(editor_cs)
    live_cluster.is_locked = True
    live_cluster.locked_by_changeset = editor_cs
    live_cluster.save()
    cdf = CustomDataField.objects.create(name="editor_field")
    ClusterData.objects.create(
        cluster=draft_cluster, field=cdf, value="draft_val", is_live=False, changeset_id=editor_cs
    )

    draft_del_url = reverse("param_admin:parameter_store_cluster_delete", args=[draft_cluster.pk])
    assert editor_client.get(draft_del_url).status_code == 200
    draft_post_resp = editor_client.post(draft_del_url, data={"post": "yes"})
    assert draft_post_resp.status_code == 302
    assert not Cluster.objects.filter(pk=draft_cluster.pk).exists()
    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is False

    # Verify user granted delete_cluster permission succeeds in staging live cluster for deletion
    deleter = User.objects.create_user("deleter", "deleter@example.com", "password", is_staff=True)
    for codename in ["view_cluster", "delete_cluster"]:
        perm = Permission.objects.get(codename=codename, content_type__app_label="parameter_store")
        deleter.user_permissions.add(perm)

    deleter_client = Client()
    deleter_client.force_login(deleter)
    del_resp = deleter_client.post(live_del_url, data={"post": "yes"})
    assert del_resp.status_code == 302
    live_cluster.refresh_from_db()
    assert live_cluster.is_locked is True
    assert Cluster.objects.filter(draft_of=live_cluster, is_pending_deletion=True).exists()
