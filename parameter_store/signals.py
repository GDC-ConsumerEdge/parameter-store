from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import ClusterDataField, Tag, ClusterTag, ClusterIntent, \
    ClusterFleetLabel, ClusterData, Cluster


def update_cluster_timestamp(cluster, updated_at):
    """Updates the 'updated_at' timestamp on a given Cluster instance.

    Args:
        updated_at: datetime
    """
    if cluster:
        Cluster.objects.filter(pk=cluster.pk).update(updated_at=updated_at)


@receiver(post_save, sender=ClusterTag)
@receiver(post_save, sender=ClusterIntent)
@receiver(post_save, sender=ClusterFleetLabel)
@receiver(post_save, sender=ClusterData)
def related_object_saved(sender, instance, **kwargs):
    """ Listens for save events on models with FK/O2O to Cluster.
    Updates the Cluster's updated_at timestamp.
    """
    cluster = None
    if hasattr(instance, 'cluster') and instance.cluster:
        cluster = instance.cluster

    if cluster:
        update_cluster_timestamp(cluster, instance.updated_at)


@receiver(post_save, sender=ClusterTag)
@receiver(post_save, sender=ClusterIntent)
@receiver(post_save, sender=ClusterFleetLabel)
@receiver(post_save, sender=ClusterData)
def related_object_deleted(sender, instance, **kwargs):
    """  Listens for delete events on models with FK/O2O to Cluster.
    Updates the Cluster's updated_at timestamp.
    """
    cluster = None
    if hasattr(instance, 'cluster') and instance.cluster:
        # Note: On deletion, the related object might already be partially gone,
        # but the foreign key reference should still be accessible here.
        cluster = instance.cluster

    if cluster:
        update_cluster_timestamp(cluster, instance.updated_at)


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
    cache.delete('tag_choices_inline')


@receiver(post_delete, sender=Tag)
def invalidate_tag_cache_on_delete(sender, **kwargs):
    cache.delete('tag_choices_inline')


@receiver(post_save, sender=ClusterDataField)
def invalidate_cluster_data_field_choices_on_save(sender, instance, **kwargs):
    cache.delete('cluster_data_field_choices')


@receiver(post_delete, sender=ClusterDataField)
def invalidate_cluster_data_field_choices_on_delete(sender, instance, **kwargs):
    cache.delete('cluster_data_field_choices')
