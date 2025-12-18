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
