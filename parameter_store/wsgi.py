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
WSGI config for parameter_store project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parameter_store.settings')

import django
if not hasattr(django, 'apps'):
    django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User

# Create migrations (if needed)
call_command('makemigrations')

# Database migrations
call_command('migrate')

# Create a superuser if one doesn't exist (maybe not, let the 1st user be superuser)
# if not User.objects.filter(is_superuser=True).exists():
#     username = os.environ.get('DJANGO_SUPERUSERNAME', 'admin')
#     email = os.environ.get('DJANGO_SUPERUSEREMAIL', 'admin@example.com')
#     password = os.environ.get('DJANGO_SUPERUSERPASSWORD', 'Ch@ngeme!')
#     User.objects.create_superuser(username=username, email=email, password=password)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
