import sys

import unfold.admin as uadmin
import unfold.sites as usites
from django.apps import apps
from django.contrib import admin

from .models import Cluster, ClusterIntent, ClusterTag, ClusterFleetLabel, Group, Tag, Validator, \
    ValidatorAssignment, ClusterData, ClusterDataField, ClusterDataFieldValidatorAssignment

app = apps.get_app_config('parameter_store')
app.verbose_name = 'Edge Parameter Store'


class HideAdmin:
    def has_module_permission(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        return {}


class ParamStoreAdmin(usites.UnfoldAdminSite):
    site_header = 'Parameter Store'
    site_title = 'Parameter Store Admin'
    index_title = 'Parameter Store Admin'

    def get_app_list(self, request, app_label=None):
        """ Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        ordering = {
            "Clusters": 1,
            "Groups": 2,
            "Tags": 3,
            "Cluster Intent": 4,
            "Cluster Tags": 5,
            "Cluster Fleet Labels": 6,
            'Cluster Custom Data Fields': 7,
            "Validators": 8,
            "Standard Validator Assignments": 9,
            "Cluster Custom Data Validator Assignments": 10,
        }
        app_dict = self._build_app_dict(request, app_label)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())

        # Sort the models alphabetically within each app.
        for app in app_list:
            app['models'].sort(key=lambda x: ordering.get(x['name'], 1000))

        return app_list


param_admin_site = ParamStoreAdmin('param_admin')


class ClusterIntentInline(uadmin.StackedInline):
    model = ClusterIntent
    extra = 0


class ClusterTagInline(uadmin.TabularInline):
    model = ClusterTag
    extra = 0


class ClusterFleetLabelsInline(uadmin.TabularInline):
    model = ClusterFleetLabel
    extra = 0


class ClusterDataInline(uadmin.TabularInline):
    model = ClusterData
    extra = 0


class ClusterDataFieldInline(uadmin.TabularInline):
    model = ClusterDataField
    extra = 0


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(uadmin.ModelAdmin):
    @admin.display(description='Cluster Tags')
    def comma_separated_tags(self, obj):
        tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)

    inlines = [ClusterDataInline, ClusterTagInline, ClusterFleetLabelsInline, ClusterIntentInline]
    list_display = ['name', 'group', 'comma_separated_tags']
    list_filter = ['name', 'group', 'tags__name']
    search_fields = ['name', 'group__name', 'tags__name']
    sortable_by = ['name', 'group']
    ordering = ['group', 'name']
    validate_on_save = True


@admin.register(Group, site=param_admin_site)
class GroupAdmin(uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']
    validate_on_save = True


@admin.register(Tag, site=param_admin_site)
class TagAdmin(uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']
    validate_on_save = True


@admin.register(ClusterFleetLabel, site=param_admin_site)
class ClusterFleetLabelAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'key', 'value']
    sortable_by = ['cluster', 'key', 'value']
    ordering = ['cluster', 'key']
    validate_on_save = True


@admin.register(ClusterTag, site=param_admin_site)
class ClusterTagAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'tag']
    sortable_by = ['cluster', 'tag']
    ordering = ['cluster', 'tag']
    validate_on_save = True


@admin.register(ClusterIntent, site=param_admin_site)
class ClusterIntentAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'zone_name', 'zone_name', 'location']
    list_filter = ['cluster']
    ordering = ['cluster']
    validate_on_save = True


@admin.register(ClusterData, site=param_admin_site)
class ClusterDataAdmin(uadmin.ModelAdmin):
    # inlines = [ClusterDataFieldInline]
    # list_display = ['cluster', 'field', 'value']
    # list_filter = ['cluster', 'field', 'value']
    # ordering = ['cluster', 'field']
    # validate_on_save = True

    def has_module_permission(self, request):
        # This prevents this model from being visible in the admin panel sidebar
        return False


@admin.register(ClusterDataField, site=param_admin_site)
class ClusterDataFieldAdmin(uadmin.ModelAdmin):
    pass


@admin.register(ClusterDataFieldValidatorAssignment, site=param_admin_site)
class ClusterDataFieldValidatorAssignmentAdmin(uadmin.ModelAdmin):
    pass


@admin.register(Validator, site=param_admin_site)
class ValidatorAdmin(uadmin.ModelAdmin):
    list_display = ['name', 'validator']
    validate_on_save = True


@admin.register(ValidatorAssignment, site=param_admin_site)
class ValidatorAssignmentAdmin(uadmin.ModelAdmin):
    list_display = ['model_field', 'validator']
    validate_on_save = True


# loads changes to admin site last
from . import admin_user_and_group  # noqa
