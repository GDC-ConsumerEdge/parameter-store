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
import importlib
import inspect
import typing
from typing import Callable

from django.utils.safestring import mark_safe

if typing.TYPE_CHECKING:
    from django.http import HttpRequest

    from .models import ChangeSet

from django.conf import settings


def get_class_from_full_path(full_path):
    module_name, class_name = full_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def inspect_callable_signature(callable: Callable):
    """Extracts and categorizes the parameters of a callable into all parameters
    and required parameters.

    This function uses the `inspect` module to analyze the signature of the
    provided callable and determines which parameters are required versus
    those that are optional. The classification of parameters considers
    their types, defaults, and the nature of the callable.

    Args:
        callable (Callable): The callable whose parameters are to be inspected.

    Returns:
        tuple: A tuple containing two lists:
            - The first list contains all parameters of the callable.
            - The second list contains only the required parameters.
    """
    params = inspect.signature(callable).parameters
    all_params, required_params = [], []
    valid_params = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    for name, param in params.items():
        if name != "self" and param.kind in valid_params:
            all_params.append(name)
            # @formatter:off
            if (
                param.kind == inspect.Parameter.POSITIONAL_ONLY
                or (param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and param.default == inspect.Parameter.empty)
                or (param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty)
            ):
                required_params.append(name)
            # @formatter:on
    return all_params, required_params


def str_to_bool(value: str | bool) -> bool:
    match value:
        case True | False:
            return value
        case str() if value.lower() in ("true", "y", "yes"):
            return True
        case str() if value.lower() in ("false", "n", "no"):
            return False
        case _:
            raise ValueError(f"{value} isn't an expected boolean value")


def get_or_create_changeset(request: "HttpRequest", create_if_none: bool = False) -> "ChangeSet":
    """Retrieves an active draft changeset for the user, optionally creating one.

    This function first checks the user's session for an 'active_changeset_id'. If a valid
    draft changeset ID is found, it returns that changeset.

    If no active changeset is found in the session, it searches for the most recent draft
    changeset for the current user. If one is found, it is set as the active changeset
    in the session and returned.

    If no draft changesets exist for the user and `create_if_none` is True, a new one
    is created, stored in the session, and then returned. Otherwise, it returns None.

    Args:
        request: The HttpRequest object, used to access the session and user information.
        create_if_none: If True, a new changeset will be created if none are found.

    Returns:
        The active ChangeSet model instance, or None if not found and not created.
    """
    from django.contrib import messages
    from django.utils import timezone

    from parameter_store.models import ChangeSet

    active_changeset_id = request.session.get("active_changeset_id")
    if active_changeset_id:
        try:
            # Ensure the active changeset is a draft
            return ChangeSet.objects.get(pk=active_changeset_id, status=ChangeSet.Status.DRAFT)
        except ChangeSet.DoesNotExist:
            # The changeset ID in the session is invalid or not a draft, so clear it.
            del request.session["active_changeset_id"]

    # No active changeset in session, try to find an existing draft changeset for the user.
    user_draft_changesets = ChangeSet.objects.filter(created_by=request.user, status=ChangeSet.Status.DRAFT).order_by(
        "-created_at"
    )

    if user_draft_changesets.exists():
        changeset = user_draft_changesets.first()
        request.session["active_changeset_id"] = changeset.id
        if create_if_none:  # Only message the user if creation was attempted
            messages.info(
                request,
                f"An operation requires an active ChangeSet. Activated your most recent draft: '{changeset.name}'",
            )
        return changeset

    if create_if_none:
        # No draft changesets exist for the user, create a new one.
        now_str = timezone.now().strftime("%Y%m%d-%H:%M:%S")
        changeset_name = f"{request.user.username}-{now_str}"
        changeset = ChangeSet.objects.create(name=changeset_name, created_by=request.user)
        request.session["active_changeset_id"] = changeset.id
        messages.info(
            request,
            f"This operation requires an active ChangeSet. A new ChangeSet {changeset.name} was created and activated.",
        )
        return changeset

    return None


def get_active_changeset_display(request: "HttpRequest") -> list | None:
    """Retrieves the active changeset and formats its name for display within the UI.

    Args:
        request: The HttpRequest object.

    Returns:
        A list containing a formatted string with the active changeset's name.
    """
    if not request.user.is_authenticated:
        return None
    # Call with create_if_none=False because this is a read-only display function.
    changeset = get_or_create_changeset(request, create_if_none=False)
    if changeset:
        display_text = f"Active ChangeSet: {changeset.name}"
        # The Unfold Admin theme applies a text-transform: capitalize, which doesn't look good
        # for the display of the active changeset. We're explicitly overriding text-transform
        # so the text displayed in the UI is as styled here
        return [mark_safe(f'<span style="text-transform: none;">{display_text}</span>'), "success"]
    else:
        display_text = "No Active ChangeSet"
        return [mark_safe(f'<span style="text-transform: none;">{display_text}</span>'), "warning"]


def reorder_homepage_dashboard(request, context):
    """Reorders homepage dashboard items given the order defined within DASHBOARD_ITEMS_ORDER in settings.py.

    Args:
        request: The HttpRequest object.
        context: The template context.

    Returns:
        The updated context dictionary.
    """

    # Get the desired order of dashboard items from settings.py
    homepage_dashboard_order = settings.UNFOLD["DASHBOARD_ITEMS_ORDER"]

    app_list = context.get("app_list", [])

    # Print a list of items which are available to order on the homepage
    if settings.DEBUG:
        print(f"DEBUG: Available homepage dashboard items: {', '.join([item['app_label'] for item in app_list])}")

    ordered_app_list = []
    for app_label in homepage_dashboard_order:
        ordered_app_list.append(next((item for item in app_list if item.get("app_label") == app_label), None))

    context["app_list"] = ordered_app_list

    return context
