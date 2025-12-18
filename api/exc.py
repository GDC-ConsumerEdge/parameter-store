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
Exception handlers for the Parameter Store API.

This module defines custom exception handlers for NinjaAPI, such as formatting
validation errors into a standard 422 response.
"""

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
