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
Django settings for parameter_store project.

It is not expected that consumers of this project manipulate this file directly.  User-overridable
configuration settings should be set from the environment.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""
import os
from pathlib import Path

from django.templatetags.static import static

from parameter_store.util import str_to_bool

version = "v1.0.0"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'

# SECURITY WARNING: keep the secret key used in production secret!
# TODO: Update this when deploying into production
# THIS VALUE IS NOT SECURE FOR PRODUCTION USE
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY',
                            'django-insecure-%yzr3^+)s&c2$4sxk702l#m0(52xd81^e40bg3tq4j+xo$wy@v')

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://' + x.strip()
    for x in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
]

# Application definition
INSTALLED_APPS = [
    'parameter_store',
    "api",
    'unfold',
    'unfold.contrib.inlines',
    'unfold.contrib.filters',
    'unfold.contrib.guardian',
    'guardian',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] if DEBUG else []

MIDDLEWARE += [
    'django.middleware.security.SecurityMiddleware',
    'servestatic.middleware.ServeStaticMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'iap_jwt.middleware.IapJwtMiddleware',
]

ROOT_URLCONF = 'parameter_store.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = 'parameter_store.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'eps'),  # Default database name is 'eps'
        'USER': os.environ.get('DB_USER', 'eps'),  # Default username
        'PASSWORD': os.environ.get('DB_PASSWORD', 's2K_Nz_gwRtjf.BCCPTmctkZ'),  # Default password
        'HOST': os.environ.get('DB_HOST', 'localhost'),  # Default host
        'PORT': os.environ.get('DB_PORT', '5432'),  # Default port
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend'
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_ROOT = 'staticfiles'

STATIC_URL = 'static/'

STORAGES = {
    "staticfiles": {
        "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

INTERNAL_IPS = ['127.0.0.1']

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_AGE = os.environ.get('PARAM_STORE_COOKIE_TTL', 3600)  # one hour default

# Param Store App Settings
UNFOLD = {
    "STYLES": [
        lambda request: static("parameter_store/css/custom_admin.css"),
    ],
}

# Defaults to enabled
IAP_ENABLED = str_to_bool(os.environ.get('PARAM_STORE_IAP_ENABLED', True))
IAP_AUDIENCE = os.environ.get('PARAM_STORE_IAP_AUDIENCE') if os.environ.get(
    'PARAM_STORE_IAP_AUDIENCE') else None
SUPERUSERS = {i for i in os.environ.get('PARAM_STORE_SUPERUSERS', '').split(',')}

API_INTERNAL_STATICFILES = str_to_bool(
    os.environ.get('PARAM_STORE_API_INTERNAL_STATICFILES', True))
if API_INTERNAL_STATICFILES:
    INSTALLED_APPS.insert(0, 'ninja')
