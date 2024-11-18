import os
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
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


trust_jwt = str_to_bool(os.environ.get('TRUST_JWT', True))
iap_enabled = str_to_bool(os.environ.get('IAP_ENABLED', True))


class IapJwtMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # pass to next middleware if JWT is not trusted
        if not trust_jwt:
            return self.get_response(request)

        if iap_enabled:
            # IAP should have JWT in header 'x_goog_iap_jwt_assertion'
            iap_jwt = request.META.get('HTTP_X_GOOG_IAP_JWT_ASSERTION')
        else:
            # Temporary code to handle jwt in local dev
            iap_jwt = request.META.get('HTTP_AUTHORIZATION')
            if iap_jwt and iap_jwt.startswith('Bearer '):
                iap_jwt = iap_jwt.split('Bearer ')[1]

        if iap_jwt:
            try:
                # Decode the JWT without verification
                decoded_token = jwt.decode(iap_jwt, options={"verify_signature": False})

                logger.debug(json.dumps(decoded_token, indent=4))

                # Extract the email
                email = decoded_token['email']

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

            except jwt.DecodeError as err:
                logger.error(f'Failed to decode JWT "{iap_jwt}": {err}')

            except KeyError:
                logger.error(f'No email found in JWT: {json.dumps(decoded_token, indent=4)}')

            except Exception as err:
                logger.error(err)

        return self.get_response(request)