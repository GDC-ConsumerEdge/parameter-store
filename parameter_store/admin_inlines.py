from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from unfold import admin as uadmin

from parameter_store.models import (
    ClusterIntent,
    Tag,
    ClusterTag,
    ClusterFleetLabel,
    CustomDataField,
    ClusterData,
    GroupData,
)


class ClusterIntentInline(uadmin.StackedInline):
    model = ClusterIntent
    extra = 0
    parent_link = True


def get_tag_choices():
    """Caches Tag choices for inline forms."""
    cache_key = "tag_choices_inline"  # Distinct cache key for inlines
    choices = cache.get(cache_key)
    if choices is None:
        choices = list(Tag.objects.values_list("id", "name"))
        cache.set(cache_key, choices, timeout=300)  # Cache for 5 minutes
    return choices


class ClusterTagInlineForm(forms.ModelForm):
    tag = forms.ChoiceField(choices=get_tag_choices)

    class Meta:
        model = ClusterTag
        fields = "__all__"

    def clean_tag(self):
        field_id = self.cleaned_data.get("tag")
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
        return super().get_queryset(request).select_related("cluster", "tag")


class ClusterFleetLabelsInline(uadmin.TabularInline):
    model = ClusterFleetLabel
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster")


def get_data_field_choices():
    """Caches ClusterDataField choices."""
    cache_key = "cluster_data_field_choices"
    choices = cache.get(cache_key)
    if choices is None:
        choices = list(CustomDataField.objects.values_list("id", "name"))
        cache.set(cache_key, choices, timeout=300)  # Cached for 5 minutes
    return choices


class DataInlineForm(ModelForm):
    field = forms.ChoiceField(choices=get_data_field_choices)

    def clean_field(self):
        field_id = self.cleaned_data.get("field")
        if field_id:
            try:
                return CustomDataField.objects.get(pk=field_id)
            except CustomDataField.DoesNotExist:
                raise ValidationError("Invalid CustomDataField.")
        return None


class ClusterDataInlineForm(DataInlineForm):
    class Meta:
        model = ClusterData
        fields = "__all__"


class ClusterDataInline(uadmin.TabularInline):
    model = ClusterData
    form = ClusterDataInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster", "field")


class GroupDataInlineForm(DataInlineForm):
    class Meta:
        model = GroupData
        fields = "__all__"


class GroupDataInline(uadmin.TabularInline):
    model = GroupData
    form = GroupDataInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "field")
