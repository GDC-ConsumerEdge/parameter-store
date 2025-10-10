from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.urls import resolve
from unfold import admin as uadmin

from parameter_store.models import (
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    ClusterTag,
    CustomDataField,
    GroupData,
    Tag,
)


class ChangeSetAwareInlineMixin(uadmin.InlineModelAdmin):
    """A mixin for admin inlines to make them aware of the parent's changeset status.

    This mixin ensures that when viewing a parent object's change page in the
    admin, the items displayed in the inline formsets are correctly filtered
    based on the parent's `is_live` status. A live parent will only show live
    inline items, and a draft parent will only show draft inline items.
    """

    def get_queryset(self, request):
        """
        Filters the queryset for the inline based on the parent object's status (live or draft).
        """
        qs = super().get_queryset(request)
        resolver_match = resolve(request.path_info)
        parent_id = resolver_match.kwargs.get("object_id")

        if parent_id:
            try:
                parent_obj = self.parent_model.objects.get(pk=parent_id)
                return qs.filter(is_live=parent_obj.is_live)
            except self.parent_model.DoesNotExist:
                return qs.none()
        return qs


class ClusterIntentInline(ChangeSetAwareInlineMixin, uadmin.StackedInline):
    model = ClusterIntent
    extra = 0
    parent_link = True
    exclude = ("changeset_id",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster")


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
        exclude = ("changeset_id",)

    def clean_tag(self):
        field_id = self.cleaned_data.get("tag")
        if field_id:
            try:
                return Tag.objects.get(pk=field_id)
            except Tag.DoesNotExist:
                raise ValidationError("Invalid Tag.")
        return None


class ClusterTagInline(ChangeSetAwareInlineMixin, uadmin.TabularInline):
    model = ClusterTag
    form = ClusterTagInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster", "tag")


class ClusterFleetLabelsInline(ChangeSetAwareInlineMixin, uadmin.TabularInline):
    model = ClusterFleetLabel
    extra = 0
    exclude = ("changeset_id",)

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
        exclude = ("changeset_id",)


class ClusterDataInline(ChangeSetAwareInlineMixin, uadmin.TabularInline):
    model = ClusterData
    form = ClusterDataInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("cluster", "field")


class GroupDataInlineForm(DataInlineForm):
    class Meta:
        model = GroupData
        exclude = ("changeset_id",)


class GroupDataInline(ChangeSetAwareInlineMixin, uadmin.TabularInline):
    model = GroupData
    form = GroupDataInlineForm
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("group", "field", "changeset_id")
