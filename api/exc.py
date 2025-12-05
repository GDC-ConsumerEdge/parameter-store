from django.core.exceptions import ValidationError
from django.http import JsonResponse


def validation_errors(request, exc: ValidationError):
    """Handles Django's ValidationError and returns a 422 Unprocessable Entity response.

    Args:
        request: The HttpRequest object.
        exc: The ValidationError instance.

    Returns:
        A JsonResponse with status 422 containing the validation error messages.
    """
    return JsonResponse({"message": exc.message_dict}, status=422)
