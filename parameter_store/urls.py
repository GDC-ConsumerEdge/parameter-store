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
URL configuration for parameter_store project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.shortcuts import redirect
from django.urls import path, include
from django.urls.conf import re_path

from . import settings
from .admin import param_admin_site
from .admin_user_and_group import admin_site

urlpatterns = [
    path('', lambda request: redirect('/params/')),
    path('admin/', admin_site.urls),
    path('params/', param_admin_site.urls),
    path('api/v1/', include('api.urls')),
    # redirect anything /api, /api/, /api/docs to /api/v1/docs
    re_path(r'^api/?(?:docs)?$', lambda request: redirect('/api/v1/docs'))
    # path('auto/', include('auto_api.urls')),

]

if settings.DEBUG:
    import debug_toolbar.toolbar

    urlpatterns += debug_toolbar.toolbar.debug_toolbar_urls()
