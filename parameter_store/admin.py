import unfold.admin as uadmin
import unfold.sites as usites
from django.apps import apps
from django.contrib import admin

from .models import Cluster, ClusterIntent, ClusterTag, ClusterFleetLabel, Group, Tag

# admin.site.site_header = 'Parameter Store'
# admin.site.site_title = 'Parameter Store Admin'
# admin.site.index_title = 'Parameter Store Admin'

app = apps.get_app_config('parameter_store')
app.verbose_name = 'Edge Parameter Store'


class ParamStoreAdmin(usites.UnfoldAdminSite):
    site_header = 'Parameter Store'
    site_title = 'Parameter Store Admin'
    index_title = 'Parameter Store Admin'

    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        ordering = {
            "Clusters": 1,
            "Groups": 2,
            "Tags": 3,
            "Cluster Intent Data": 4,
            "Cluster Tags": 5,
            "Cluster Fleet Labels": 6
        }
        app_dict = self._build_app_dict(request)

        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())

        # Sort the models alphabetically within each app.
        for app in app_list:
            app['models'].sort(key=lambda x: ordering[x['name']])

        return app_list


param_admin_site = ParamStoreAdmin('param_admin')


class ClusterIntentInline(uadmin.StackedInline):
    model = ClusterIntent
    extra = 1


class ClusterTagInline(uadmin.TabularInline):
    model = ClusterTag
    extra = 1


class ClusterFleetLabels(uadmin.TabularInline):
    model = ClusterFleetLabel
    extra = 1


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(uadmin.ModelAdmin):
    @admin.display(description='Cluster Tags')
    def comma_separated_tags(self, obj):
        tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)

    inlines = [ClusterTagInline, ClusterIntentInline]
    list_display = ['name', 'group', 'comma_separated_tags']
    list_filter = ['name', 'group', 'tags__name']
    search_fields = ['name', 'group__name', 'tags__name']
    sortable_by = ['name', 'group']
    ordering = ['group', 'name']


@admin.register(Group, site=param_admin_site)
class GroupAdmin(uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']


@admin.register(Tag, site=param_admin_site)
class TagAdmin(uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']


@admin.register(ClusterFleetLabel, site=param_admin_site)
class ClusterFleetLabelAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'key', 'value']
    sortable_by = ['cluster', 'key', 'value']
    ordering = ['cluster', 'key']


@admin.register(ClusterTag, site=param_admin_site)
class ClusterTagAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'tag']
    sortable_by = ['cluster', 'tag']
    ordering = ['cluster', 'tag']


@admin.register(ClusterIntent, site=param_admin_site)
class ClusterIntentAdmin(uadmin.ModelAdmin):
    list_display = ['cluster', 'zone_id', 'zone_name', 'location']
    list_filter = ['cluster']
    ordering = ['cluster']
