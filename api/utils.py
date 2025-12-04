import functools
import logging
from typing import Callable

from ninja.errors import HttpError

logger = logging.getLogger(__name__)


def require_permissions(*permissions: str) -> Callable:
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
    """Paginates a queryset by applying a limit and offset.

    Args:
        queryset (QuerySet): The Django QuerySet to paginate.
        limit (int): The maximum number of items to return.
        offset (int): The starting index from which to return items.

    Returns:
        QuerySet: A subset of the original queryset based on the limit and offset.
    """

    return queryset[offset : offset + limit]
