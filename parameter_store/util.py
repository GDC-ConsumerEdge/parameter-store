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


def get_or_create_changeset(request: "HttpRequest") -> "ChangeSet":
    """Retrieves the active changeset from the session or creates a new one.

    This function checks the user's session for an 'active_changeset_id'. If found, it
    retrieves the corresponding ChangeSet object. If not found, it creates a new
    ChangeSet, names it with the user's username and the current timestamp, stores its
    ID in the session, and informs the user via a message.

    Args:
        request: The HttpRequest object, used to access the session and user information.

    Returns:
        The active ChangeSet model instance.
    """
    from django.contrib import messages
    from django.utils import timezone

    from parameter_store.models import ChangeSet

    active_changeset_id = request.session.get("active_changeset_id")
    if active_changeset_id:
        try:
            return ChangeSet.objects.get(pk=active_changeset_id)
        except ChangeSet.DoesNotExist:
            # The changeset ID in the session is invalid, so we'll create a new one.
            del request.session["active_changeset_id"]

    now_str = timezone.now().strftime("%Y%m%d-%H:%M:%S")
    changeset_name = f"ChangeSet {request.user.username} {now_str}"
    changeset = ChangeSet.objects.create(name=changeset_name, created_by=request.user)
    request.session["active_changeset_id"] = changeset.id
    messages.info(request, f"No active changeset. Created and activated a new one: {changeset.name}")
    return changeset


def get_active_changeset_display(request: "HttpRequest") -> list | None:
    """Retrieves the active changeset and formats its name for display within the UI.

    Args:
        request: The HttpRequest object.

    Returns:
        A list containing a formatted string with the active changeset's name.
    """
    if not request.user.is_authenticated:
        return None
    changeset = get_or_create_changeset(request)
    if changeset:
        display_text = f"Active ChangeSet: {changeset.name}"
        # The Unfold Admin theme applies a text-transform: capitalize, which doesn't look good
        # for the display of the active changeset. We're explicitly overriding text-transform
        # so the text displayed in the UI is as styled here
        return [mark_safe(f'<span style="text-transform: none;">{display_text}</span>'), "success"]
    else:
        display_text = "Active ChangeSet: None"
        return [mark_safe(f'<span style="text-transform: none;">{display_text}</span>'), "warning"]
