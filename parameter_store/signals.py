import datetime
from typing import Type

from django.core.cache import cache
from django.db.models import Model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    ClusterTag,
    CustomDataField,
    Group,
    GroupData,
    Tag,
)


def update_timestamp(model: Type[Model], parent_instance: Group | Cluster, updated_at: datetime.datetime):
    """Updates the 'updated_at' timestamp on a given Cluster or Group instance.

    Args:
        model: model/table to search for parent object
        parent_instance: related object that we are searching to update
        updated_at: datetime of change
    """
    if parent_instance:
        model.objects.filter(pk=parent_instance.pk).update(updated_at=updated_at)


@receiver((post_save, post_delete), sender=ClusterTag)
@receiver((post_save, post_delete), sender=ClusterIntent)
@receiver((post_save, post_delete), sender=ClusterFleetLabel)
@receiver((post_save, post_delete), sender=ClusterData)
@receiver((post_save, post_delete), sender=GroupData)
def related_object_saved(sender, *, instance, **kwargs):
    """Listens for save and delete events on models with FK/O2O to Cluster.
    Updates the Cluster or Group's updated_at timestamp.
    """
    this = None
    if hasattr(instance, "cluster") and instance.cluster:
        this = instance.cluster
    elif hasattr(instance, "group") and instance.group:
        this = instance.group

    upd_at = timezone.now() if kwargs.get("signal") else instance.updated_at

    match this:
        case Cluster():
            update_timestamp(Cluster, this, upd_at)
        case Group():
            update_timestamp(Group, this, upd_at)


# This is intentionally dark code; leaving this commented out.
# We don't have m2m relationships currently because we're using through tables, but that doesn't
# mean we won't ever have them.  This should work with few changes if needed.
# # We listen to the M2M field on the Cluster model directly
# @receiver(m2m_changed, sender=Cluster.tags.through)  # '.through' gets the intermediate model
# def tags_changed_on_cluster(sender, instance, action, pk_set, **kwargs):
#     """  Listens for changes on the Cluster.tags ManyToMany relationship.
#     Updates the Cluster's updated_at timestamp.
#
#     'instance' here is the Cluster instance.
#     'action' can be 'pre_add', 'post_add', 'pre_remove', 'post_remove', 'pre_clear', 'post_clear'.
#     'pk_set' is a set of primary keys of the related objects (Tags) being added/removed.
#     """
#     # We only care about actions that actually modify the relationship
#     if action in ['post_add', 'post_remove', 'post_clear']:
#         if isinstance(instance, Cluster):
#             update_cluster_timestamp(instance, instance.updated_at)


@receiver(post_save, sender=Tag)
def invalidate_tag_cache_on_save(sender, **kwargs):
    cache.delete("tag_choices_inline")


@receiver(post_delete, sender=Tag)
def invalidate_tag_cache_on_delete(sender, **kwargs):
    cache.delete("tag_choices_inline")


@receiver(post_save, sender=CustomDataField)
def invalidate_cluster_data_field_choices_on_save(sender, instance, **kwargs):
    cache.delete("cluster_data_field_choices")


@receiver(post_delete, sender=CustomDataField)
def invalidate_cluster_data_field_choices_on_delete(sender, instance, **kwargs):
    cache.delete("cluster_data_field_choices")
