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
from django.utils.deprecation import MiddlewareMixin


class DisableCsrfForApiMiddleware(MiddlewareMixin):
    """
    Middleware to disable CSRF protection for API endpoints.

    This is necessary because the API uses session authentication (via django_auth
    and IapJwtMiddleware), which triggers Django's standard CSRF protection.
    However, API clients (robots, scripts) and IAP-authenticated calls should
    not be burdened with CSRF token management.
    """

    def process_request(self, request):
        if request.path.startswith("/api/v1/"):
            setattr(request, "_dont_enforce_csrf_checks", True)
