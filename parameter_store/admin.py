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
import unfold.sites as usites
from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .admin_inlines import (
    ClusterIntentInline,
    ClusterTagInline,
    ClusterFleetLabelsInline,
    ClusterDataInline,
    GroupDataInline,
)
from .models import (
    Cluster,
    ClusterIntent,
    ClusterTag,
    ClusterFleetLabel,
    Group,
    Tag,
    Validator,
    ValidatorAssignment,
    ClusterData,
    CustomDataField,
    CustomDataFieldValidatorAssignment,
    GroupData,
)


class ParamStoreAdmin(usites.UnfoldAdminSite):
    site_header = "Edge Parameter Store"
    site_title = "Edge Parameter Store"
    index_title = "Edge Parameter Store"

    def get_app_list(self, request, app_label=None):
        """Return a sorted list of all the installed apps that have been registered to this
        site.
        """
        ordering = {
            "Clusters": 1,
            "Groups": 2,
            "Tags": 3,
            "Cluster Intent": 4,
            "Cluster Fleet Labels": 6,
            "Cluster Custom Data Fields": 7,
            "Cluster Custom Data": 8,
            "Validators": 9,
            "Standard Data Validator Assignments": 10,
            "Cluster Custom Data Validator Assignments": 11,
        }
        app_dict = self._build_app_dict(request, app_label)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x["name"].lower())

        # Sort the models alphabetically within each app.
        for app in app_list:
            app["models"].sort(key=lambda x: ordering.get(x["name"], 1000))

        return app_list


param_admin_site = ParamStoreAdmin("param_admin")


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [ClusterDataInline, ClusterTagInline, ClusterFleetLabelsInline, ClusterIntentInline]
    list_display = ["name", "group", "comma_separated_tags"]
    list_filter = ["group", "tags__name"]
    search_fields = ["name", "group__name", "tags__name"]
    sortable_by = ["name", "group"]
    ordering = ["group", "name"]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Cluster Tags")
    def comma_separated_tags(self, obj):
        # Now tags are prefetched, so this is efficient
        if hasattr(obj, "prefetched_tags"):  # Check if prefetch is available, for testing
            tags = obj.prefetched_tags
        else:
            tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)
        return ""

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "intent").prefetch_related("tags")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            kwargs["queryset"] = Tag.objects.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Group, site=param_admin_site)
class GroupAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [GroupDataInline]
    list_display = ["name"]
    sortable_by = ["name"]
    ordering = ["name"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(Tag, site=param_admin_site)
class TagAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["name"]
    sortable_by = ["name"]
    ordering = ["name"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClusterTag, site=param_admin_site)
class ClusterTagAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(ClusterFleetLabel, site=param_admin_site)
class ClusterFleetLabelAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["cluster", "key", "value"]
    sortable_by = ["cluster", "key", "value"]
    ordering = ["cluster", "key"]
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(ClusterIntent, site=param_admin_site)
class ClusterIntentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["cluster", "zone_name", "zone_name", "location"]
    list_filter = ["cluster"]
    ordering = ["cluster"]
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(CustomDataField, site=param_admin_site)
class ClusterDataFieldAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")


@admin.register(ClusterData, site=param_admin_site)
class ClusterDataAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster", "field")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(GroupData, site=param_admin_site)
class GroupDataAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "field")

    def has_module_permission(self, request, **kwargs):
        # Return False to hide the model from the admin
        return False


@admin.register(Validator, site=param_admin_site)
class ValidatorAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["name", "validator"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ValidatorAssignment, site=param_admin_site)
class ValidatorAssignmentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ["model_field", "validator"]
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomDataFieldValidatorAssignment, site=param_admin_site)
class ClusterDataFieldValidatorAssignmentAdmin(uadmin.ModelAdmin):
    list_display = ["field", "validator"]
    readonly_fields = ("created_at", "updated_at")
