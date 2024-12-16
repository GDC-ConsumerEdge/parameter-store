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
from django import forms
from django.apps import apps
from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from guardian.admin import GuardedModelAdmin

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
    site_title = 'Parameter Store'
    index_title = 'Parameter Store'

    def get_app_list(self, request, app_label=None):
        """ Return a sorted list of all the installed apps that have been registered to this
        site.
        """
        ordering = {
            "Clusters": 1,
            "Groups": 2,
            "Tags": 3,
            "Cluster Intent": 4,
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


def get_tag_choices():
    """Caches Tag choices for inline forms."""
    cache_key = 'tag_choices_inline'  # Distinct cache key for inlines
    choices = cache.get(cache_key)
    if choices is None:
        choices = list(Tag.objects.values_list('id', 'name'))
        cache.set(cache_key, choices, timeout=300)  # Cache for 5 minutes
    return choices


@receiver(post_save, sender=Tag)
def invalidate_tag_cache_on_save(sender, **kwargs):
    cache.delete('tag_choices_inline')


@receiver(post_delete, sender=Tag)
def invalidate_tag_cache_on_delete(sender, **kwargs):
    cache.delete('tag_choices_inline')


class ClusterTagInlineForm(forms.ModelForm):
    tag = forms.ChoiceField(choices=get_tag_choices)

    class Meta:
        model = ClusterTag
        fields = '__all__'

    def clean_tag(self):
        print('in clean_tag')
        field_id = self.cleaned_data.get('tag')
        if field_id:
            try:
                return Tag.objects.get(pk=field_id)
            except Tag.DoesNotExist:
                raise ValidationError("Invalid Tag.")
        return None


class ClusterTagInline(uadmin.TabularInline):
    model = ClusterTag
    form = ClusterTagInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cluster', 'tag')


class ClusterFleetLabelsInline(uadmin.TabularInline):
    model = ClusterFleetLabel
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cluster')


def get_cluster_data_field_choices():
    """Caches ClusterDataField choices."""
    cache_key = 'cluster_data_field_choices'
    choices = cache.get(cache_key)
    if choices is None:
        choices = list(
            ClusterDataField.objects.values_list('id', 'name'))
        cache.set(cache_key, choices, timeout=300)  # Cached for 5 minutes
    return choices


@receiver(post_save, sender=ClusterDataField)
def invalidate_cluster_data_field_choices_on_save(sender, instance, **kwargs):
    cache.delete('cluster_data_field_choices')


@receiver(post_delete, sender=ClusterDataField)
def invalidate_cluster_data_field_choices_on_delete(sender, instance, **kwargs):
    cache.delete('cluster_data_field_choices')


class ClusterDataInlineForm(forms.ModelForm):
    field = forms.ChoiceField(choices=get_cluster_data_field_choices)

    class Meta:
        model = ClusterData
        fields = '__all__'

    def clean_field(self):
        field_id = self.cleaned_data.get('field')
        if field_id:
            try:
                return ClusterDataField.objects.get(pk=field_id)
            except ClusterDataField.DoesNotExist:
                raise ValidationError("Invalid ClusterDataField.")
        return None


class ClusterDataInline(uadmin.TabularInline):
    model = ClusterData
    form = ClusterDataInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cluster', 'field')


@admin.register(Cluster, site=param_admin_site)
class ClusterAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    inlines = [ClusterDataInline, ClusterTagInline, ClusterFleetLabelsInline, ClusterIntentInline]
    list_display = ['name', 'group', 'comma_separated_tags']
    list_filter = ['group', 'tags__name']
    search_fields = ['name', 'group__name', 'tags__name']
    sortable_by = ['name', 'group']
    ordering = ['group', 'name']
    validate_on_save = True

    @admin.display(description='Cluster Tags')
    def comma_separated_tags(self, obj):
        # Now tags are prefetched, so this is efficient
        if hasattr(obj, 'prefetched_tags'):  # Check if prefetch is available, for testing
            tags = obj.prefetched_tags
        else:
            tags = obj.tags.all()
        if tags:
            return ", ".join(tag.name for tag in tags)
        return ""

    def get_queryset(self, request):
        return super().get_queryset(request)\
            .select_related('group', 'clusterintent')\
            .prefetch_related('tags')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tags":
            kwargs["queryset"] = Tag.objects.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Group, site=param_admin_site)
class GroupAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']
    validate_on_save = True


@admin.register(Tag, site=param_admin_site)
class TagAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['name']
    sortable_by = ['name']
    ordering = ['name']
    validate_on_save = True


@admin.register(ClusterFleetLabel, site=param_admin_site)
class ClusterFleetLabelAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['cluster', 'key', 'value']
    sortable_by = ['cluster', 'key', 'value']
    ordering = ['cluster', 'key']
    validate_on_save = True


@admin.register(ClusterIntent, site=param_admin_site)
class ClusterIntentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['cluster', 'zone_name', 'zone_name', 'location']
    list_filter = ['cluster']
    ordering = ['cluster']
    validate_on_save = True


@admin.register(ClusterDataField, site=param_admin_site)
class ClusterDataFieldAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    pass


@admin.register(Validator, site=param_admin_site)
class ValidatorAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['name', 'validator']
    validate_on_save = True


@admin.register(ValidatorAssignment, site=param_admin_site)
class ValidatorAssignmentAdmin(GuardedModelAdmin, uadmin.ModelAdmin):
    list_display = ['pretty_field', 'validator']
    validate_on_save = True

    @admin.display(description='Model Field')
    def pretty_field(self, obj):
        return f'{obj.model.split('.')[2]}.{obj.model_field}'


@admin.register(ClusterDataFieldValidatorAssignment, site=param_admin_site)
class ClusterDataFieldValidatorAssignmentAdmin(uadmin.ModelAdmin):
    list_display = ['field', 'validator']
    validate_on_save = True


# loads changes to admin site last
from . import admin_user_and_group  # noqa
