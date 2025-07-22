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
ASGI config for parameter_store project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

import django
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.management import call_command
from servestatic import ServeStaticASGI

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parameter_store.settings")

if not hasattr(django, "apps"):
    django.setup()

# Migrations should be an explicit operation run elsewhere. We don't want to have the app
# makemigrations in prod dynamically at runtime in an uncontrolled manner.
# call_command('makemigrations')

# Database migrations
call_command("migrate")

application = get_asgi_application()
application = ServeStaticASGI(application, root=settings.STATIC_ROOT)
