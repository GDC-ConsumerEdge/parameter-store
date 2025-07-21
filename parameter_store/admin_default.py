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
import unfold.admin as uadmin
import unfold.sites
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm


class CustomAdminSite(unfold.sites.UnfoldAdminSite):
    site_header = "Parameter Store Admin"
    site_title = "Parameter Store Admin"
    index_title = "Parameter Store Admin"

    def has_permission(self, request):
        return request.user.is_superuser


admin_site = CustomAdminSite(name="custom_admin")


class UserAdmin(BaseUserAdmin, uadmin.ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


class GroupAdmin(BaseGroupAdmin, uadmin.ModelAdmin):
    pass


admin_site.register(User, UserAdmin)
admin_site.register(Group, GroupAdmin)
