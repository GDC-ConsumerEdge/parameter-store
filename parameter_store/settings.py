###############################################################################
# Copyright 2026 Google, LLC
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

import colorsys
import os
from pathlib import Path

from django.templatetags.static import static
from django.urls import reverse_lazy

from parameter_store.customerconfig import img_path, primary_color_hex
from parameter_store.util import str_to_bool

version = "v1.0.0"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

# SECURITY WARNING: keep the secret key used in production secret!
# TODO: Update this when deploying into production
# THIS VALUE IS NOT SECURE FOR PRODUCTION USE
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-%yzr3^+)s&c2$4sxk702l#m0(52xd81^e40bg3tq4j+xo$wy@v")

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = ["https://" + x.strip() for x in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")]

# Application definition
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.inlines",
    "unfold.contrib.filters",
    "unfold.contrib.guardian",
    "guardian",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "parameter_store",
    "api",
]

if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] if DEBUG else []

MIDDLEWARE += [
    "django.middleware.security.SecurityMiddleware",
    "servestatic.middleware.ServeStaticMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "parameter_store.middleware.changeset_middleware",
    "django.middleware.common.CommonMiddleware",
    "api.middleware.DisableCsrfForApiMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "iap_jwt.middleware.IapJwtMiddleware",
]

ROOT_URLCONF = "parameter_store.urls"

TEMPLATES = [
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
                "parameter_store.context_processors.changeset_context",
            ],
        },
    },
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
    },
]

WSGI_APPLICATION = "parameter_store.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "eps"),  # Default database name is 'eps'
        "USER": os.environ.get("DB_USER", "eps"),  # Default username
        "PASSWORD": os.environ.get("DB_PASSWORD", "s2K_Nz_gwRtjf.BCCPTmctkZ"),  # Default password
        "HOST": os.environ.get("DB_HOST", "localhost"),  # Default host
        "PORT": os.environ.get("DB_PORT", "5432"),  # Default port
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "guardian.backends.ObjectPermissionBackend"]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

USE_I18N = True

USE_TZ = True
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_ROOT = "staticfiles"

STATIC_URL = "static/"

STORAGES = {
    "staticfiles": {
        "BACKEND": "servestatic.storage.CompressedManifestStaticFilesStorage",
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

INTERNAL_IPS = ["127.0.0.1"]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_AGE = os.environ.get("PARAM_STORE_COOKIE_TTL", 3600)  # one hour default


# generate hls color palette based on company color hex
def generate_hls_palette(hex_color):
    hex_color = hex_color.lstrip("#")

    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    h, l, s = colorsys.rgb_to_hls(r, g, b)  # noqa: E741 (l is an accepted variable name in this context)
    palette = {}

    shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]

    for shade in shades:
        if shade <= 500:
            new_l = l + (500 - shade) / 500 * (1 - l)
        else:
            new_l = l * (500 / shade)

        new_r, new_g, new_b = colorsys.hls_to_rgb(h, new_l, s)
        r, g, b = int(new_r * 255), int(new_g * 255), int(new_b * 255)
        new_hex = f"#{r:02x}{g:02x}{b:02x}"

        palette[str(shade)] = new_hex

    return palette


# Param Store App Settings
UNFOLD = {
    "STYLES": [
        # CSS customizations for this app
        lambda request: static("css/custom_admin.css"),
        # Enabling support for Unfold Tailwind customization:
        # https://unfoldadmin.com/docs/styles-scripts/customizing-tailwind/
        lambda request: static("css/styles.css"),
    ],
    "USER_LINKS": [
        {"template": "unfold/helpers/userlinks.html"},
    ],
    "SITE_HEADER": "Parameter Store",
    "SITE_TITLE": "Parameter Store",
    "SITE_SYMBOL": "app_registration",
    # Enable the ability to specify the order of items which appear on the site homepage
    "DASHBOARD_CALLBACK": "parameter_store.util.reorder_homepage_dashboard",
    # Enable env variable DJANGO_DEBUG=True to console log all available dashboard items
    "DASHBOARD_ITEMS_ORDER": ["parameter_store"],
    # Repurpose this setting to display the currently active ChangeSet
    "ENVIRONMENT": "parameter_store.util.get_active_changeset_display",
    "COLORS": {
        "base": {
            "50": "249 250 251",
            "100": "243 244 246",
            "200": "229 231 235",
            "300": "209 213 219",
            "400": "156 163 175",
            "500": "107 114 128",
            "600": "75 85 99",
            "700": "55 65 81",
            "800": "31 41 55",
            "900": "17 24 39",
            "950": "3 7 18",
        },
        "primary": generate_hls_palette(primary_color_hex),
        "font": {
            "subtle-light": "var(--color-base-500)",  # text-base-500
            "subtle-dark": "var(--color-base-400)",  # text-base-400
            "default-light": "var(--color-base-600)",  # text-base-600
            "default-dark": "var(--color-base-300)",  # text-base-300
            "important-light": "var(--color-base-900)",  # text-base-900
            "important-dark": "var(--color-base-100)",  # text-base-100
        },
    },
    "SIDEBAR": {
        "show_search": False,  # Search in applications and models names
        "command_search": False,  # Replace the sidebar search with the command search
        "show_all_applications": False,  # Dropdown with all applications and models
        "navigation": [
            {
                # "title": "ChangeSets",
                "icon": "rebase_edit",
                "collapsible": False,
                "items": [
                    {
                        "title": "ChangeSets",
                        "icon": "rebase_edit",
                        "link": reverse_lazy("admin:parameter_store_changeset_changelist"),
                    },
                ],
            },
            {
                "title": "Clusters",
                "collapsible": True,
                "items": [
                    {
                        "title": "Clusters",
                        "icon": "host",
                        "link": reverse_lazy("admin:parameter_store_cluster_changelist"),
                    },
                    {
                        "title": "Groups",
                        "icon": "linked_services",
                        "link": reverse_lazy("admin:parameter_store_group_changelist"),
                    },
                    {
                        "title": "Tags",
                        "icon": "sell",
                        "link": reverse_lazy("admin:parameter_store_tag_changelist"),
                    },
                    {
                        "title": "Cluster Intent",
                        "icon": "schema",
                        "link": reverse_lazy("admin:parameter_store_clusterintent_changelist"),
                    },
                    {
                        "title": "Cluster Fleet Labels",
                        "icon": "label",
                        "link": reverse_lazy("admin:parameter_store_clusterfleetlabel_changelist"),
                    },
                    {
                        "title": "Cluster Custom Data Fields",
                        "icon": "people",
                        "link": reverse_lazy("admin:parameter_store_customdatafield_changelist"),
                    },
                    {
                        "title": "Cluster Custom Data",
                        "icon": "people",
                        "link": reverse_lazy("admin:parameter_store_clusterdata_changelist"),
                    },
                ],
            },
            {
                "title": ("Validators"),
                "collapsible": True,
                "permission": lambda request: request.user.is_superuser,
                "items": [
                    {
                        "title": "ChangeSet Validators",
                        "icon": "checklist",
                        "link": reverse_lazy("admin:parameter_store_validator_changelist"),
                    },
                    {
                        "title": "Standard Data Validator Assignments",
                        "icon": "data_check",
                        "link": reverse_lazy("admin:parameter_store_validatorassignment_changelist"),
                    },
                    {
                        "title": "Cluster Custom Data Validator Assignments",
                        "icon": "edit_attributes",
                        "link": reverse_lazy("admin:parameter_store_customdatafieldvalidatorassignment_changelist"),
                    },
                ],
            },
            {
                "title": ("Users & Groups"),
                "collapsible": True,
                "permission": lambda request: request.user.is_superuser,
                "items": [
                    {
                        "title": ("Users"),
                        "icon": "account_circle",
                        "link": reverse_lazy("param_admin:auth_user_changelist"),
                    },
                    {
                        "title": ("Groups"),
                        "icon": "group",
                        "link": reverse_lazy("param_admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
}

# if company logo exists, add as site_icon and favicons
if img_path:
    UNFOLD["SITE_ICON"] = lambda request: static(img_path)
    UNFOLD["SITE_FAVICONS"] = [
        {"rel": "icon", "sizes": "32x32", "type": "image/svg+xml", "href": lambda request: static(img_path)}
    ]

# Defaults to enabled
IAP_ENABLED = str_to_bool(os.environ.get("PARAM_STORE_IAP_ENABLED", True))
IAP_AUDIENCE = os.environ.get("PARAM_STORE_IAP_AUDIENCE") if os.environ.get("PARAM_STORE_IAP_AUDIENCE") else None
SUPERUSERS = {i for i in os.environ.get("PARAM_STORE_SUPERUSERS", "").split(",")}

API_INTERNAL_STATICFILES = str_to_bool(os.environ.get("PARAM_STORE_API_INTERNAL_STATICFILES", True))
if API_INTERNAL_STATICFILES:
    INSTALLED_APPS.insert(0, "ninja")

try:
    from .local_settings import *  # noqa: F403
except ImportError:
    pass
