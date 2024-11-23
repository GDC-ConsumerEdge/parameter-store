import os
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
import logging
import json

# Get an instance of a logger
logger = logging.getLogger(__name__)


def str_to_bool(value:str|bool) -> bool:
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
                    certs_url = "https://www.gstatic.com/iap/verify/public_key") if (
                    iap_enabled) else id_token.verify_token(iap_jwt, req)
                logger.debug(json.dumps(id_info, indent=4))

                # Extract the email
                if 'email' in id_info.keys():
                    email = id_info['email']
                else:
                    logger.error(f'No email found in JWT: {json.dumps(id_info, indent=4)}')
                    return self.get_response(request)

                # Get or create the user
                if User.objects.filter(is_superuser=True).exists():
                    # Superuser exists, make this user a staff user
                    user, created = User.objects.get_or_create(
                        username=email,
                        defaults={'email': email, 'is_staff': True}
                    )
                else:
                    # No superuser exists, make this user a superuser
                    user, created = User.objects.get_or_create(
                        username=email,
                        defaults={'email': email, 'is_staff': True, 'is_superuser': True}
                    )

                # Trust the JWT and Authenticate the user
                login(request, user)

            except ValueError as err:
                logger.error(f'Failed to validate JWT "{iap_jwt}": {err}')

            except Exception as err:
                logger.error(err)

        return self.get_response(request)