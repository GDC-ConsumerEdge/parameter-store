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
import logging
import uuid
from collections import defaultdict

from django.conf import settings  # Required for ForeignKey to User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.query import Prefetch
from django.utils import timezone

from parameter_store.constraints import top_level_constraints
from parameter_store.util import get_class_from_full_path, inspect_callable_signature
from parameter_store.validation import BaseValidator

logger = logging.getLogger(__name__)


class DynamicValidatingModel(models.Model):
    """Provides an abstract base class with dynamic validation capabilities.

    This class serves as a foundation for models requiring dynamic validation
    based on external validator configurations. It accomplishes this by
    associating validator assignments to specific model fields, enabling field
    values to be validated against a wide range of criteria defined outside
    the model itself. The validation mechanism is invoked by the `clean`
    method, ensuring that all field validations are executed prior to saving
    the model. This approach supports dynamic model validation customization
    and centralizes the validation logic.

    :ivar Meta.abstract: Indicates that this is an abstract model class, which
        will not itself create a database table.
    :type Meta.abstract: bool
    """

    class Meta:
        abstract = True  # Abstract classes won’t create a database table

    def clean(self, validator_assignment_model=None) -> None:
        """
        Cleans and validates the current instance against a set of validators.

        The method first logs the process of validation, then retrieves all
        `ValidatorAssignment` instances that are associated with the current
        class by filtering on its module and name. Each validator is instantiated
        with its parameters, and then applied on the specified model field.
        Any validation errors are collected and, if any are found, a
        `ValidationError` is raised with all collected errors.

        :raises TypeError: If the validator is instantiated with invalid
            parameters.
        :raises AttributeError: If a `ValidatorAssignment` references an
            invalid field for the model.
        :raises ValidationError: If any of the validators fail validation.
        """

        logger.debug(f"Validating {self.__class__.__name__} with parameters: {self.__dict__!r} ")
        super().clean()

        this_class = self.__class__.__module__ + "." + self.__class__.__name__

        errors = defaultdict(list)
        for va in ValidatorAssignment.objects.filter(model=this_class):
            Validator = get_class_from_full_path(va.validator.validator)

            try:
                validator = Validator(**va.validator.parameters)
            except TypeError:
                logger.error(f"Invalid parameters for validator {va.validator.name}: {va.validator.parameters}")
                raise

            model, field_name = va.model_field.split(".")

            try:
                field = getattr(self, field_name)
            except AttributeError:
                logger.error(
                    f"ValidatorAssignment {va.id} references invalid field {va.model_field} for model {this_class}"
                )
                raise

            try:
                validator.validate(field)
            except ValidationError as e:
                logger.info("Validation error", e)
                errors[field_name].append(e)

        if errors:
            raise ValidationError(errors)


class ChangeSet(models.Model):
    """A collection of data modifications (creations, updates, or deletions)
    staged together.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMMITTED = "committed", "Committed"
        ABANDONED = "abandoned", "Abandoned"

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="A user-defined name for easy identification of the ChangeSet",
    )
    description = models.TextField(
        blank=True, null=True, help_text="An optional text field for more detailed notes about the ChangeSet"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,  # TODO: Evaluate. Seems likely to be queried/filtered on, but remove if not.
        help_text="The current state of the ChangeSet",
    )
    created_by = models.ForeignKey(
        # Assumes standard Django User model
        settings.AUTH_USER_MODEL,
        # Don't delete ChangeSet if user is deleted; or models.SET_NULL if appropriate
        on_delete=models.PROTECT,
        related_name="change_sets_created",
        help_text="The user who created this ChangeSet",
    )
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="change_sets_committed",
        null=True,
        blank=True,
        help_text="The user who committed this ChangeSet",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the ChangeSet was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the ChangeSet was last updated")
    committed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the ChangeSet was committed")

    def __str__(self):
        return f"{self.name or f'ChangeSet {self.id}'} ({self.get_status_display()})"

    def commit(self, user):
        """Commits the changeset, making its changes live."""
        from django.db import transaction
        from django.utils import timezone

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        if self.status != self.Status.DRAFT:
            raise ValueError(f"ChangeSet '{self.name}' is not in draft state.")

        top_level_models = [Group, Cluster]
        child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

        with transaction.atomic():
            # Process top-level entities
            for model in top_level_models:
                draft_entities = model.objects.filter(changeset_id=self.id, is_live=False)
                for draft_entity in draft_entities:
                    live_entity = (
                        model.objects.filter(shared_entity_id=draft_entity.shared_entity_id, is_live=True).first()
                        if draft_entity.shared_entity_id
                        else None
                    )

                    if draft_entity.is_pending_deletion:
                        if live_entity:
                            # "Retire" the live entity instead of deleting it
                            live_entity.is_locked = False
                            live_entity.locked_by_changeset = None
                            live_entity.is_live = False
                            live_entity.obsoleted_by_changeset = self
                            live_entity.save()

                            # Retire associated live child entities manually since we aren't deleting the parent
                            for child_model in child_models:
                                # Determine the ForeignKey name pointing to the parent model
                                fk_name = model.__name__.lower()
                                filter_kwargs = {fk_name: live_entity, "is_live": True}
                                try:
                                    child_model.objects.filter(**filter_kwargs).update(is_live=False)
                                except Exception:
                                    # Some child models might not link to this parent type (e.g. GroupData doesn't link to Cluster)
                                    pass

                        # Delete children of the draft entity to satisfy foreign key constraints (specifically DO_NOTHING on ClusterTag)
                        for child_model in child_models:
                            fk_name = model.__name__.lower()
                            try:
                                child_model.objects.filter(**{fk_name: draft_entity}).delete()
                            except Exception:
                                pass

                        # The draft's purpose was just to signal deletion; it is now consumed.
                        draft_entity.delete()
                        continue

                    if live_entity:
                        # Demote old live
                        live_entity.is_locked = False
                        live_entity.locked_by_changeset = None
                        live_entity.is_live = False
                        live_entity.obsoleted_by_changeset = self
                        live_entity.save()

                        # Promote draft
                        draft_entity.is_live = True
                        draft_entity.changeset_id = None
                        draft_entity.is_locked = False
                        draft_entity.locked_by_changeset = None
                        draft_entity.draft_of = None
                        draft_entity.save()

                        # Cascade updates
                        if model == Group:
                            Cluster.objects.filter(group=live_entity).update(group=draft_entity)
                            clusters_with_secondary = Cluster.objects.filter(secondary_groups=live_entity)
                            for cluster in clusters_with_secondary:
                                cluster.secondary_groups.remove(live_entity)
                                cluster.secondary_groups.add(draft_entity)
                    else:
                        # New entity
                        draft_entity.is_live = True
                        draft_entity.changeset_id = None
                        draft_entity.is_locked = False
                        draft_entity.locked_by_changeset = None
                        draft_entity.draft_of = None
                        draft_entity.save()

            # Process child entities (that were drafted directly, e.g. edits to children)
            for model in child_models:
                draft_entities = model.objects.filter(changeset_id=self.id, is_live=False)
                for draft_entity in draft_entities:
                    draft_entity.is_live = True
                    draft_entity.changeset_id = None
                    draft_entity.save()

            self.status = self.Status.COMMITTED
            self.committed_at = timezone.now()
            self.committed_by = user
            self.save()

    def abandon(self):
        """Abandons the changeset, deleting drafts and unlocking parents."""
        from django.db import transaction

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        if self.status != self.Status.DRAFT:
            raise ValueError(f"ChangeSet '{self.name}' is not in draft state.")

        top_level_models = [Group, Cluster]
        child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

        with transaction.atomic():
            # Unlock parent live entities
            for model in top_level_models:
                locked_live_entities = model.objects.filter(locked_by_changeset=self, is_live=True)
                for entity in locked_live_entities:
                    entity.is_locked = False
                    entity.locked_by_changeset = None
                    entity.save()

            # Delete draft rows
            for model in top_level_models:
                model.objects.filter(changeset_id=self.id, is_live=False).delete()

            for model in child_models:
                model.objects.filter(changeset_id=self.id, is_live=False).delete()

            self.status = self.Status.ABANDONED
            self.save()

    def coalesce(self, target_changeset):
        """Merges this changeset into a target changeset and deletes self."""
        from django.db import transaction

        from .models import Cluster, ClusterData, ClusterFleetLabel, ClusterIntent, ClusterTag, Group, GroupData

        if self.status != self.Status.DRAFT:
            raise ValueError(f"Source ChangeSet '{self.name}' is not in draft state.")
        if target_changeset.status != self.Status.DRAFT:
            raise ValueError(f"Target ChangeSet '{target_changeset.name}' is not in draft state.")

        top_level_models = [Group, Cluster]
        child_models = [ClusterTag, ClusterIntent, ClusterFleetLabel, ClusterData, GroupData]

        with transaction.atomic():
            # Re-point locks
            for model in top_level_models:
                model.objects.filter(locked_by_changeset=self).update(locked_by_changeset=target_changeset)

            # Move draft entities
            for model in top_level_models:
                model.objects.filter(changeset_id=self.id).update(changeset_id=target_changeset.id)

            for model in child_models:
                model.objects.filter(changeset_id=self.id).update(changeset_id=target_changeset.id)

            self.delete()

    class Meta:
        verbose_name = "ChangeSet"
        verbose_name_plural = "ChangeSets"
        ordering = ["-created_at"]


class ChangeSetAwareTopLevelEntity(models.Model):
    """
    A top level entity that is aware of its ChangeSet.  This is a mixin class.  Current top level entities are
    Clusters and Groups.
    """

    class Meta:
        abstract = True

    shared_entity_id = models.UUIDField(editable=False, db_index=True, null=False, default=uuid.uuid4)
    is_live = models.BooleanField(editable=False, db_index=True, null=False, default=False)
    is_locked = models.BooleanField(editable=False, db_index=True, null=False, default=False)
    changeset_id = models.ForeignKey(
        ChangeSet, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ChangeSet ID", related_name="+"
    )
    locked_by_changeset = models.ForeignKey(
        ChangeSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Locked by ChangeSet",
        related_name="+",
    )
    obsoleted_by_changeset = models.ForeignKey(
        ChangeSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Obsoleted by ChangeSet",
        related_name="+",
    )
    draft_of = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="drafts")
    is_pending_deletion = models.BooleanField(
        default=False, editable=False, help_text="Marks a draft entity for deletion upon commit."
    )

    def create_draft(self, changeset, is_pending_deletion=False):
        """Creates a draft copy of this entity within a changeset.

        Args:
            changeset: The changeset to associate with the new draft.
            is_pending_deletion: If True, marks the draft for deletion.

        Returns:
            The newly created draft instance.
        """
        # Create a new instance in memory
        draft_instance = self.__class__()

        # Copy attributes from the original instance
        for field in self._meta.fields:
            # Don't copy the primary key
            if field.primary_key:
                continue
            setattr(draft_instance, field.name, getattr(self, field.name))

        # Set the new state for the draft
        draft_instance.shared_entity_id = self.shared_entity_id
        draft_instance.is_live = False
        draft_instance.is_locked = False
        draft_instance.changeset_id = changeset
        draft_instance.draft_of = self
        draft_instance.is_pending_deletion = is_pending_deletion
        draft_instance.save()

        # Now that the draft has a PK, we can set M2M relationships
        for field in self._meta.many_to_many:
            getattr(draft_instance, field.name).set(getattr(self, field.name).all())

        # Copy the child relations from the original to the new draft
        self.copy_child_relations(draft_instance, changeset)

        # If the model being copied is a Group, we need to check if there are any
        # draft Clusters in the same changeset that need their group FK updated.
        if self.__class__.__name__ == "Group":
            # Avoid circular import
            Cluster = self._meta.apps.get_model("parameter_store", "Cluster")
            clusters_in_changeset = Cluster.objects.filter(changeset_id=changeset.id, is_live=False)
            for cluster in clusters_in_changeset:
                if cluster.group_id == self.pk:
                    cluster.group = draft_instance
                    cluster.save()

        return draft_instance

    def copy_child_relations(self, draft_instance, changeset):
        """Handles the deep copying of child relationships for a new draft instance.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement copy_child_relations")


class ChangeSetAwareChildEntity(models.Model):
    class Meta:
        abstract = True

    is_live = models.BooleanField(editable=False, db_index=True, default=False)
    changeset_id = models.ForeignKey(
        ChangeSet, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ChangeSet ID"
    )


class Group(ChangeSetAwareTopLevelEntity, DynamicValidatingModel):
    class Meta:
        constraints = top_level_constraints + [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_live=True),
                name="unique_live_group_name",
            ),
        ]

    name = models.CharField(db_index=True, max_length=30, blank=False, unique=False, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def copy_child_relations(self, draft_instance, changeset):
        # Iterate over all custom data related to the original group.
        for group_data in self.group_data.all():
            # Setting pk and id to None ensures that a new object will be created.
            group_data.pk = None
            group_data.id = None
            # Link the new child object to the draft group.
            group_data.group = draft_instance
            # Mark the new child object as a draft.
            group_data.is_live = False
            # Associate the new child object with the active changeset.
            group_data.changeset_id = changeset
            group_data.save()


class Tag(DynamicValidatingModel):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False, verbose_name="Tag Name")
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ClusterManager(models.Manager):
    """
    Custom manager class for handling cluster-related queries.  Used by the Cluster model.   This is necessary because
    unoptimized queries for clusters have abysmal performance.

    This manager subclass provides an additional method for query optimizations specific to clusters. It extends the
    default manager to include complex QuerySets with related objects, enhancing performance and reducing database
    queries by using `select_related` and `prefetch_related`.
    """

    # def get_queryset(self):
    #     return super().get_queryset()

    def with_related(self):
        """
        Fetches the queryset with related objects using select_related and prefetch_related.

        This method optimizes database queries by selecting and prefetching related objects
        to reduce the number of queries needed for retrieving associated data.

        This method is NOT an override.

        Returns:
            QuerySet: An optimized queryset with related objects included.

        Raises:
            None
        """
        return (
            self.get_queryset()
            .select_related("group", "intent")
            .prefetch_related(
                "tags",
                "fleet_labels",
                "secondary_groups",
                Prefetch("cluster_data", queryset=ClusterData.objects.select_related("field")),
            )
        )


class Cluster(ChangeSetAwareTopLevelEntity, DynamicValidatingModel):
    class Meta:
        constraints = top_level_constraints

    name = models.CharField(
        db_index=True, max_length=30, blank=False, unique=False, null=False, verbose_name="Cluster Name"
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING)
    secondary_groups = models.ManyToManyField(Group, blank=True, related_name="secondary_clusters")
    tags = models.ManyToManyField("Tag", through="ClusterTag", blank=True, related_name="clusters")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ClusterManager()

    def __str__(self):
        return self.name

    def copy_child_relations(self, draft_instance, changeset):
        # Iterate over all custom data related to the original cluster.
        for cluster_data in self.cluster_data.all():
            cluster_data.pk = None
            cluster_data.id = None
            cluster_data.cluster = draft_instance
            cluster_data.is_live = False
            cluster_data.changeset_id = changeset
            cluster_data.save()

        # Iterate over all fleet labels related to the original cluster.
        for fleet_label in self.fleet_labels.all():
            fleet_label.pk = None
            fleet_label.id = None
            fleet_label.cluster = draft_instance
            fleet_label.is_live = False
            fleet_label.changeset_id = changeset
            fleet_label.save()

        # Check if the original cluster has an intent and copy it.
        if hasattr(self, "intent"):
            intent = self.intent
            intent.pk = None
            intent.id = None
            intent.cluster = draft_instance
            intent.is_live = False
            intent.changeset_id = changeset
            intent.save()

    @property
    def tags_list(self):
        return self.tags.all()

    @property
    def fleet_labels_list(self):
        return self.fleet_labels.all()

    @property
    def data_list(self):
        # TODO: check if this is needed; initial look seems like instance attribute `data` does not exist
        return self.data.all()


class ClusterTag(ChangeSetAwareChildEntity, DynamicValidatingModel):
    class Meta:
        verbose_name = "Cluster Tag"
        verbose_name_plural = "Cluster Tags"

    cluster = models.ForeignKey(Cluster, on_delete=models.DO_NOTHING)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cluster.name} - {self.tag.name}"


class ClusterIntent(ChangeSetAwareChildEntity, DynamicValidatingModel):
    class Meta:
        verbose_name = "Cluster Intent"
        verbose_name_plural = "Cluster Intent"
        constraints = [
            models.UniqueConstraint(
                fields=["unique_zone_id"],
                condition=models.Q(is_live=True),
                name="unique_live_clusterintent_zone_id",
            )
        ]

    cluster = models.OneToOneField(Cluster, on_delete=models.CASCADE, related_name="intent")
    unique_zone_id = models.CharField(
        max_length=64,
        verbose_name="Unique Zone ID",
        help_text='A user-defined name of the zone, sometimes referred to as "store_id"',
    )
    zone_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Zone Name",
        help_text="Name of the GDCc zone name (e.g., us-west1-edge-mtv55)",
    )
    location = models.CharField(
        max_length=30, null=False, help_text="A GCP region where machines are associated (e.g., us-west1)"
    )
    machine_project_id = models.CharField(
        max_length=30,
        null=False,
        verbose_name="Machine Project ID",
        help_text="Project ID where machines are associated",
    )
    fleet_project_id = models.CharField(
        max_length=30, null=False, verbose_name="Fleet Project ID", help_text="Project ID of the fleet"
    )
    secrets_project_id = models.CharField(
        max_length=30, null=False, verbose_name="Secrets Project ID", help_text="Project ID for secrets"
    )
    node_count = models.IntegerField(null=False, default=3, help_text="Number of nodes in the cluster. Defaults to 3")
    cluster_ipv4_cidr = models.CharField(
        max_length=18,
        null=False,
        verbose_name="Cluster IPv4 CIDR",
        help_text="IPv4 CIDR range with which to provision the control plane of the cluster (e.g., 192.168.0.0/24)",
    )
    services_ipv4_cidr = models.CharField(
        max_length=18,
        null=False,
        verbose_name="Services IPv4 CIDR",
        help_text="IPv4 CIDR range to use for Kubernetes Services (e.g., 192.168.1.0/24)",
    )
    external_load_balancer_ipv4_address_pools = models.CharField(
        max_length=180,
        null=False,
        verbose_name="External Load Balancer IPv4 Address Pools",
        help_text="IPv4 CIDR used by Kubernetes for Services of type LoadBalancer (e.g., 192.168.2.0/24)",
    )
    sync_repo = models.CharField(
        max_length=128,
        null=False,
        verbose_name="Sync Repo",
        help_text="A complete URL to a Git repository containing configuration data for this cluster",
    )
    sync_branch = models.CharField(
        max_length=50,
        null=False,
        default="main",
        verbose_name="Sync Branch",
        help_text="The Git branch within the Git repository containing configuration data for this cluster (e.g., main)",
    )
    sync_dir = models.CharField(
        max_length=50,
        null=False,
        default="hydrated/clusters/",
        verbose_name="Sync Directory",
        help_text="A directory within the Git branch containing configuration data for this cluster (e.g., /hydrated/clusters)",
    )
    git_token_secrets_manager_name = models.CharField(
        max_length=255,
        null=False,
        verbose_name="Git Token GCP Secrets Manager Name",
        help_text="The name of a GCP Secrets Manager secret that contains a Git authorization token",
    )
    cluster_version = models.CharField(
        max_length=30,
        null=False,
        verbose_name="Cluster Version",
        help_text="The GDCc version to be installed (e.g., 1.11.0)",
    )
    maintenance_window_start = models.DateTimeField(
        null=True, blank=True, verbose_name="Maintenance Window Start", help_text=None
    )
    maintenance_window_end = models.DateTimeField(
        null=True, blank=True, verbose_name="Maintenance Window End", help_text=None
    )
    maintenance_window_recurrence = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        verbose_name="Maintenance Window Recurrence Rule",
        help_text="A RFC 5545 recurrence rule (e.g., FREQ=WEEKLY;BYDAY=WE,TH,FR)",
    )
    maintenance_exclusion_name_1 = models.CharField(
        null=True,
        blank=True,
        max_length=64,
        verbose_name="Maintenance Exclusion Rule Name",
        help_text="The name of a maintenance exclusion rule (e.g., Black Friday-Cyber Monday)",
    )
    maintenance_exclusion_start_1 = models.DateTimeField(
        null=True, blank=True, verbose_name="Maintenance Exclusion Rule Start", help_text=None
    )
    maintenance_exclusion_end_1 = models.DateTimeField(
        null=True, blank=True, verbose_name="Maintenance Exclusion Rule End", help_text=None
    )
    subnet_vlans = models.CharField(
        max_length=128,
        null=True,
        verbose_name="Secondary Network VLAN IDs",
        help_text="A comma-separated list of VLAN IDs for secondary networks (e.g., 500,2100,2500)",
    )
    recreate_on_delete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.cluster.name


class ClusterFleetLabel(ChangeSetAwareChildEntity, DynamicValidatingModel):
    class Meta:
        verbose_name = "Cluster Fleet Label"
        verbose_name_plural = "Cluster Fleet Labels"
        constraints = [models.UniqueConstraint(fields=["cluster", "key"], name="unique_cluster_key")]

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name="fleet_labels")
    key = models.CharField(max_length=63, blank=False, null=False)
    value = models.CharField(max_length=63, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.cluster.name} - "{self.key}" = "{self.value}"'


class CustomDataField(models.Model):
    class Meta:
        verbose_name = "Custom Data Field"
        verbose_name_plural = "Custom Data Fields"

    name = models.CharField(max_length=64, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CustomDataValidatingModel(models.Model):
    field: "models.ForeignKey"

    class Meta:
        abstract = True

    def clean(self, validator_assignment_model=None) -> None:
        """
        Cleans and validates the current instance against a set of validators.

        The method first logs the process of validation, then retrieves all
        `ValidatorAssignment` instances that are associated with the current
        class by filtering on its module and name. Each validator is instantiated
        with its parameters, and then applied on the specified model field.
        Any validation errors are collected and, if any are found, a
        `ValidationError` is raised with all collected errors.

        :raises TypeError: If the validator is instantiated with invalid
            parameters.
        :raises AttributeError: If a `ValidatorAssignment` references an
            invalid field for the model.
        :raises ValidationError: If any of the validators fail validation.
        """
        logger.debug(f"Validating {self.__class__.__name__} with parameters: {self.__dict__!r} ")
        super().clean()

        errors = defaultdict(list)
        for va in CustomDataFieldValidatorAssignment.objects.filter(field=self.field.id):
            Validator = get_class_from_full_path(va.validator.validator)

            try:
                validator = Validator(**va.validator.parameters)
            except TypeError:
                logger.error(f"Invalid parameters for validator {va.validator.name}: {va.validator.parameters}")
                raise

            try:
                validator.validate(self.value)
            except ValidationError as e:
                logger.info("Validation error", e)
                errors["field"].append(e)

        if errors:
            raise ValidationError(errors)


class ClusterData(ChangeSetAwareChildEntity, CustomDataValidatingModel):
    class Meta:
        verbose_name = "Cluster Custom Data"
        verbose_name_plural = "Cluster Custom Data"
        constraints = [models.UniqueConstraint(fields=["cluster", "field"], name="unique_cluster_field")]

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name="cluster_data")
    field = models.ForeignKey(CustomDataField, on_delete=models.CASCADE)
    value = models.CharField(max_length=1024, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.cluster.name} - "{self.field.name}" = "{self.value}"'


class GroupData(ChangeSetAwareChildEntity, CustomDataValidatingModel):
    class Meta:
        verbose_name = "Group Custom Data"
        verbose_name_plural = "Group Custom Data"
        constraints = [models.UniqueConstraint(fields=["group", "field"], name="unique_group_field")]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_data")
    field = models.ForeignKey(CustomDataField, on_delete=models.CASCADE)
    value = models.CharField(max_length=1024, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.group.name} - "{self.field.name}" = "{self.value}"'


def get_validator_choices():
    """Returns a list of tuples representing custom validator classes."""
    validators = [cls for cls in BaseValidator.__subclasses__()]
    return [(val.__module__ + "." + val.__name__, val.__name__) for val in validators]


def get_model_choices():
    """This is where models which should have validation enabled should be registered.  Add or
    remove models from the `_validation_enabled_models` tuple below.

    Returns a list of tuples representing Django model classes.
    Each tuple contains a string representing the import path of the model
    and a string representing the name of the model.
    """
    _validation_enabled_models = (Group, Cluster, Tag, ClusterTag, ClusterIntent, ClusterFleetLabel)

    choices = [(model.__module__ + "." + model.__name__, model.__name__) for model in _validation_enabled_models]
    return choices


def get_model_field_choices():
    """Return a list of tuples representing all fields of all registered models."""

    _validation_enabled_models = (Group, Cluster, Tag, ClusterTag, ClusterIntent, ClusterFleetLabel)

    model_field_choices = []
    for ModelClass in _validation_enabled_models:
        for field in ModelClass._meta.fields:
            if field.name != "id":
                model_field_path = f"{ModelClass.__name__}.{field.name}"
                model_field_choices.append((model_field_path, model_field_path))

    return model_field_choices


class Validator(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, null=False)
    validator = models.CharField(max_length=255, blank=False, null=False, choices=get_validator_choices())
    parameters = models.JSONField(
        default=dict,
        blank=True,
        null=False,
        help_text="Enter parameters for the validator in JSON format. Due to limitations in the UI, arguments for "
        "validators cannot be displayed dynamically. Contents of this field will be validated and feedback "
        "will be provided.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def clean(self):
        if not isinstance(self.parameters, dict):
            self.parameters = {}

        validator = get_class_from_full_path(self.validator)
        errors = defaultdict(list)

        all_args, required_args = inspect_callable_signature(validator.__init__)
        print(all_args, required_args)
        for k in self.parameters:
            if k not in all_args:
                errors["parameters"].append(f'Parameter "{k}" not supported in validator "{validator.__name__}"')

        for k in required_args:
            if k not in self.parameters:
                errors["parameters"].append(f'Parameter "{k}" is required in validator "{validator.__name__}"')

        if errors:
            errors["parameters"].append(f"Expected arguments: {required_args or 'none'}")
            raise ValidationError(errors)


class ValidatorAssignment(models.Model):
    validator = models.ForeignKey(Validator, on_delete=models.CASCADE)
    model = models.CharField(
        max_length=255, null=False, choices=get_model_choices(), help_text="Model to apply validator"
    )
    model_field = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        choices=get_model_field_choices(),
        verbose_name="Model Field",
        help_text="Select model and it's field",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Standard Data Validator Assignment"
        verbose_name_plural = "Standard Data Validator Assignments"
        constraints = [
            models.UniqueConstraint(fields=["model", "model_field", "validator"], name="unique_model_field_validator")
        ]

    def __str__(self):
        return f"{self.model_field} - {self.validator.name}"

    def clean(self):
        cls = get_class_from_full_path(self.model)
        model, field_name = self.model_field.split(".")
        if not hasattr(cls, field_name):
            raise ValidationError({"model_field": f'Model "{cls.__name__}" does not have field "{self.model_field}"'})


class CustomDataFieldValidatorAssignment(models.Model):
    class Meta:
        verbose_name = "Custom Data Validator Assignment"
        verbose_name_plural = "Custom Data Validator Assignments"
        constraints = [models.UniqueConstraint(fields=["field", "validator"], name="unique_field_validator")]

    field = models.ForeignKey(CustomDataField, on_delete=models.DO_NOTHING)
    validator = models.ForeignKey(Validator, on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Field "{self.field.name}" - Validator "{self.validator.name}"'
