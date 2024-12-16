import functools
import logging
from typing import Callable

from ninja import NinjaAPI

logger = logging.getLogger(__name__)


def require_permissions(api: NinjaAPI, *permissions: list[str]) -> Callable:
    def decorator(func):
        @functools.wraps(func)
        def wrapped(request, *args, **kwargs):
            logger.info(f'Checking permissions on {func.__name__} for {request.user}')
            has_perms = request.user.has_perms(permissions)
            if not has_perms:
                return api.create_response(request, {'message': 'Permission denied'}, status=403)
            return func(request, *args, **kwargs)

        return wrapped

    return decorator


def paginate(queryset, limit, offset):
    """ Paginates a queryset by applying a limit and offset.

    Args:
        queryset (QuerySet): The Django QuerySet to paginate.
        limit (int): The maximum number of items to return.
        offset (int): The starting index from which to return items.

    Returns:
        QuerySet: A subset of the original queryset based on the limit and offset.
    """

    return queryset[offset:offset + limit]
