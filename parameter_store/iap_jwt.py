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
import os

from django.contrib.auth import login
from django.contrib.auth.models import User
from google.auth.transport import requests
from google.oauth2 import id_token

# Get an instance of a logger
logger = logging.getLogger(__name__)


def str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    value = value.lower()
    try:
        value = float(value)
        return bool(value)
    except ValueError as err:
        if value in ['true', 't', 'y', 'yes']:
            return True
        elif value in ['false', 'f', 'n', 'no']:
            return False
        else:
            raise err


iap_enabled = str_to_bool(os.environ.get('IAP_ENABLED', True))


class IapJwtMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # request -> django.core.handlers.wsgi.WSGIRequest

        if iap_enabled:
            # IAP should have JWT in header 'x_goog_iap_jwt_assertion'
            iap_jwt = request.META.get('HTTP_X_GOOG_IAP_JWT_ASSERTION')
        else:
            # Otherwise it should be in the header 'Authorization'
            iap_jwt = request.META.get('HTTP_AUTHORIZATION')
            if iap_jwt and iap_jwt.startswith('Bearer '):
                iap_jwt = iap_jwt.split('Bearer ')[1]

        if iap_jwt:
            try:
                req = requests.Request()
                # IAP public keys are stored in a different URL than generic google public keys
                id_info = id_token.verify_token(
                    iap_jwt, req,
                    certs_url="https://www.gstatic.com/iap/verify/public_key") if (
                    iap_enabled) else id_token.verify_token(iap_jwt, req)
                logger.debug(json.dumps(id_info, indent=4))

                # Extract the email
                if 'email' in id_info.keys():
                    email = id_info['email']
                else:
                    logger.error(f'No email found in JWT: {json.dumps(id_info, indent=4)}')
                    return self.get_response(request)

                # Get or create the user
                user, _ = User.objects.get_or_create(
                    username=email,
                    defaults={'email': email, 'is_staff': True}
                )

                # Trust the JWT and Authenticate the user
                login(request, user)

            except ValueError as err:
                logger.error(f'Failed to validate JWT "{iap_jwt}": {err}')

            except Exception as err:
                logger.error(err)

        return self.get_response(request)
