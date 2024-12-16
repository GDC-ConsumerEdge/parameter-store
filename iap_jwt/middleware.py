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
import json
import logging
from typing import Callable

import google.auth.exceptions
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponse
from google.auth.transport import requests
from google.oauth2 import id_token

# Get an instance of a logger
logger = logging.getLogger(__name__)


class IapJwtMiddleware:
    """GCP Identity-Aware Proxy (IAP) JWT authentication middleware.

    This middleware authenticates requests using a JSON Web Token (JWT)
    provided by Google Cloud Platform's Identity-Aware Proxy. It verifies the
    token and logs in the user based on the email extracted from the JWT.
    """

    def __init__(self, get_response: Callable) -> None:
        """Initialize the middleware with the given response callback.

        Args:
            get_response: The callable that returns the next middleware or view.
        """
        self.get_response = get_response

    def __call__(self, request) -> HttpResponse:
        """Process each incoming request to authenticate using IAP JWT.

        This method checks for a JWT in either the 'x_goog_iap_jwt_assertion'
        header (when IAP is enabled) or the 'Authorization' header. It verifies
        the token and logs in the user based on the email extracted from the JWT.
        If authentication fails, it continues processing the request without
        modifying the response.

        Args:
            request: The Django request object to process.

        Returns:
            The response returned by the next middleware or view.
        """
        # IAP should have JWT in header 'x_goog_iap_jwt_assertion'
        jwt = request.META.get('HTTP_X_GOOG_IAP_JWT_ASSERTION')

        if jwt:
            try:
                req = requests.Request()
                # IAP public keys are stored in a different URL than generic google public keys
                token = id_token.verify_token(
                    jwt,
                    req,
                    audience=settings.IAP_AUDIENCE,
                    certs_url="https://www.gstatic.com/iap/verify/public_key")

                # Extract the email
                email = token.get('email')
                if not email:
                    logger.error(f'No email found in JWT: {json.dumps(token, indent=4)}')
                    return self.get_response(request)

                username = email.split('@')[0]

                # Get or create the user
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'is_staff': True,
                        'is_superuser': True if username in settings.SUPERUSERS else False
                    }
                )

                if created:
                    logger.info(f'Created new user via IAP JWT: {user.username}')

                # Trust the JWT and Authenticate the user
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                logger.info(f'Logged in via IAP JWT: {user.username}')

            except ValueError as err:
                logger.error(f'Failed to validate JWT "{jwt[:10]}...": {err}')

            except google.auth.exceptions.GoogleAuthError as err:
                logger.error(err)
        else:
            logger.info(f'IAP middleware is enabled but no IAP JWT found in headers')

        return self.get_response(request)
