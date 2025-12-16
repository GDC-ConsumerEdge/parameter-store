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
    pass


@pytest.fixture
def admin_site():
    return AdminSite()


@pytest.fixture
def group_admin(admin_site):
    return MockGroupAdmin(Group, admin_site)


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def user():
    return User.objects.create_superuser("admin", "admin@example.com", "password")


def test_delete_view_intercepts_live_object(group_admin, rf, user):
    """
    Test that delete_view intercepts POST requests for live objects,
    stages them for deletion, and redirects without actual deletion.
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
