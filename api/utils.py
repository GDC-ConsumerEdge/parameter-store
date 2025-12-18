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
Utility functions for the Parameter Store API.

Contains decorators for permission checking and common data manipulation
helpers like pagination.
"""

import functools
import logging
from typing import Callable

from ninja.errors import HttpError

logger = logging.getLogger(__name__)


def require_permissions(*permissions: str) -> Callable:
    """
    Decorator that checks if the user has at least one of the specified permissions.

    Args:
        *permissions: Variable length list of permission codenames to check.

    Returns:
        Callable: The decorated function.

    Raises:
        HttpError: 403 Forbidden if the user lacks all specified permissions.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapped(request, *args, **kwargs):
            logger.info(f"Checking for permissions {permissions} on {func.__name__} for {request.user}")
            if not any(request.user.has_perm(perm) for perm in permissions):
                raise HttpError(403, "Permission denied")
            return func(request, *args, **kwargs)

        return wrapped

    return decorator


def paginate(queryset, limit, offset):
    """
    Paginates a queryset by applying a limit and offset.

    Args:
        queryset (QuerySet): The Django QuerySet to paginate.
        limit (int): The maximum number of items to return.
        offset (int): The starting index from which to return items.

    Returns:
        QuerySet: A subset of the original queryset based on the limit and offset.
    """

    return queryset[offset : offset + limit]
