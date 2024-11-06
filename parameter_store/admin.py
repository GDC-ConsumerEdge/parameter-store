from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered

from .models import Cluster, ClusterIntent, ClusterTag

# class ParameterStoreAdmin(admin.AdminSite):
#     site_header = 'Parameter Store'
#     site_title = 'Parameter Store Admin'
#     index_title = 'Welcome to the Parameter Store Admin'
#
#     def has_permission(self, request):
#         return request.user.is_superuser
# param_store_admin = ParameterStoreAdmin(name='param_store_admin')

admin.site.site_header = 'Parameter Store'
admin.site.site_title = 'Parameter Store Admin'
admin.site.index_title = 'Parameter Store Admin'

app = apps.get_app_config('parameter_store')
app.verbose_name = 'Edge Parameter Store'


class ClusterIntentInline(admin.StackedInline):
    model = ClusterIntent
    extra = 1


class ClusterTagInline(admin.StackedInline):
    model = ClusterTag
    extra = 1


class ClusterAdmin(admin.ModelAdmin):
    inlines = [ClusterTagInline, ClusterIntentInline]
    list_display = ['name', 'group']
    sortable_by = ['name', 'group']


admin.site.register(Cluster, ClusterAdmin)

for model_name, model in app.models.items():
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        pass
