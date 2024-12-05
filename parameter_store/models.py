import inspect
import logging
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import models

from parameter_store.util import get_class_from_full_path, inspect_callable_signature
from parameter_store.validation import BaseValidator

logger = logging.getLogger(__name__)


class DynamicValidatingModel(models.Model):
    """ Provides an abstract base class with dynamic validation capabilities.

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

        logger.debug(f'Validating {self.__class__.__name__} with parameters: {self.__dict__!r} ')
        super().clean()

        this_class = self.__class__.__module__ + '.' + self.__class__.__name__

        errors = defaultdict(list)
        for va in ValidatorAssignment.objects.filter(model=this_class):
            Validator = get_class_from_full_path(va.validator.validator)

            try:
                validator = Validator(**va.validator.parameters)
            except TypeError:
                logger.error(f'Invalid parameters for validator '
                             f'{va.validator.name}: {va.validator.parameters}')
                raise

            try:
                field = getattr(self, va.model_field)
            except AttributeError:
                logger.error(f'ValidatorAssignment {va.id} references invalid '
                             f'field {va.model_field} for model {this_class}')
                raise

            try:
                validator.validate(field)
            except ValidationError as e:
                logger.info("Validation error", e)
                errors[va.model_field].append(e)

        if errors:
            raise ValidationError(errors)


# class CustomDataValidatingModel(models.Model):
#     """ Provides an abstract base class with dynamic validation capabilities.
#
#     This class serves as a foundation for models requiring dynamic validation
#     based on external validator configurations. It accomplishes this by
#     associating validator assignments to specific model fields, enabling field
#     values to be validated against a wide range of criteria defined outside
#     the model itself. The validation mechanism is invoked by the `clean`
#     method, ensuring that all field validations are executed prior to saving
#     the model. This approach supports dynamic model validation customization
#     and centralizes the validation logic.
#
#     :ivar Meta.abstract: Indicates that this is an abstract model class, which
#         will not itself create a database table.
#     :type Meta.abstract: bool
#     """
#
#     class Meta:
#         abstract = True  # Abstract classes won’t create a database table
#



class Group(DynamicValidatingModel):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Cluster(DynamicValidatingModel):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING)
    tags = models.ManyToManyField(
        'Tag',
        through='ClusterTag',
        related_name='clusters',
    )

    def __str__(self):
        return self.name


class Tag(DynamicValidatingModel):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False,
                            verbose_name='tag name')
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ClusterTag(DynamicValidatingModel):
    class Meta:
        verbose_name = 'Cluster Tag'
        verbose_name_plural = 'Cluster Tags'

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.cluster.name} - {self.tag.name}'


class ClusterIntent(DynamicValidatingModel):
    class Meta:
        verbose_name = 'Cluster Intent'
        verbose_name_plural = 'Cluster Intent'

    cluster = models.OneToOneField(Cluster, on_delete=models.CASCADE)
    zone_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=None)
    location = models.CharField(
        max_length=30,
        null=False,
        help_text=None)
    machine_project_id = models.CharField(
        max_length=30,
        null=False,
        verbose_name='Machine Project ID',
        help_text=None)
    fleet_project_id = models.CharField(
        max_length=30,
        null=False,
        verbose_name='Fleet Project ID',
        help_text=None)
    secrets_project_id = models.CharField(
        max_length=30,
        null=False,
        help_text=None)
    node_count = models.IntegerField(
        null=False,
        default=3,
        help_text=None)
    cluster_ipv4_cidr = models.CharField(
        max_length=18,
        null=False,
        verbose_name='Cluster IPv4 CIDR',
        help_text=None)
    services_ipv4_cidr = models.CharField(
        max_length=18,
        null=False,
        verbose_name='Services IPv4 CIDR',
        help_text=None)
    external_load_balancer_ipv4_address_pools = models.CharField(
        max_length=180,
        null=False,
        verbose_name='External Load Balancer IPv4 Address Pools',
        help_text=None)
    sync_repo = models.CharField(
        max_length=128,
        null=False,
        help_text='This is the full URL to a Git repository')
    sync_branch = models.CharField(
        max_length=50,
        null=False,
        default='main',
        help_text='For; example: "main" or "master"')
    sync_dir = models.CharField(
        max_length=50,
        null=False,
        default=f'hydrated/clusters/{cluster.name}',
        help_text=None)
    git_token_secret_manager_name = models.CharField(
        max_length=255,
        null=False,
        help_text=None)
    cluster_version = models.CharField(
        max_length=30,
        null=False,
        help_text='This is the GDCC control plane version, i.e. "1.7.1"')
    maintenance_window_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text=None)
    maintenance_window_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text=None)
    maintenance_window_recurrence = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text=None)
    subnet_vlans = models.CharField(
        max_length=128,
        null=True,
        help_text=None)
    recreate_on_delete = models.BooleanField(default=False)

    def __str__(self):
        return self.cluster.name


class ClusterFleetLabel(DynamicValidatingModel):
    class Meta:
        verbose_name = 'Cluster Fleet Label'
        verbose_name_plural = 'Cluster Fleet Labels'
        constraints = [
            models.UniqueConstraint(fields=['cluster', 'key'], name='unique_cluster_key')
        ]

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    key = models.CharField(max_length=63, blank=False, null=False)
    value = models.CharField(max_length=63, blank=False, null=False)

    def __str__(self):
        return f'{self.cluster.name} - "{self.key}" = "{self.value}"'


def get_validator_choices():
    """Returns a list of tuples representing custom validator classes.
    """
    validators = [cls for cls in BaseValidator.__subclasses__()]
    return [(val.__module__ + '.' + val.__name__, val.__name__) for val in validators]


def get_model_choices():
    """ This is where models which should have validation enabled should be registered.  Add or
    remove models from the `_validation_enabled_models` tuple below.

    Returns a list of tuples representing Django model classes.
    Each tuple contains a string representing the import path of the model
    and a string representing the name of the model.
    """
    _validation_enabled_models = (
        Group, Cluster, Tag, ClusterTag, ClusterIntent, ClusterFleetLabel
    )

    return [(model.__module__ + '.' + model.__name__, model.__name__)
            for model in _validation_enabled_models]


def get_model_field_choices():
    """Return a list of tuples representing all fields of all registered models."""

    _validation_enabled_models = (
        Group, Cluster, Tag, ClusterTag, ClusterIntent, ClusterFleetLabel
    )

    model_field_choices = []
    for ModelClass in _validation_enabled_models:
        for field in ModelClass._meta.fields:
            if field.name != 'id':
                model_field_path = f"{ModelClass.__name__}.{field.name}"
                model_field_choices.append((field.name, model_field_path))

    return model_field_choices


class Validator(models.Model):
    name = models.CharField(
        max_length=255,
        unique=True,
        blank=False,
        null=False)
    validator = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        choices=get_validator_choices())
    parameters = models.JSONField(
        default=dict,
        blank=True,
        null=False,
        help_text="Enter parameters for the validator in JSON format. Due to limitations in the "
                  "UI, arguments for validators cannot be displayed dynamically. Contents of "
                  "this field will be validated and feedback will be provided on the contents of "
                  "this field."
    )

    def __str__(self):
        return self.name

    def clean(self):
        validator = get_class_from_full_path(self.validator)
        errors = defaultdict(list)

        all_args, required_args = inspect_callable_signature(validator.__init__)
        print(all_args, required_args)
        for k in self.parameters:
            if k not in all_args:
                errors['parameters'].append(
                    f'Parameter "{k}" not supported in validator "{validator.__name__}"')

        for k in required_args:
            if k not in self.parameters:
                errors['parameters'].append(
                    f'Parameter "{k}" is required in validator "{validator.__name__}"')

        if errors:
            errors['parameters'].append(f'Expected arguments: {required_args or 'none'}')
            raise ValidationError(errors)


class ValidatorAssignment(models.Model):
    validator = models.ForeignKey(Validator, on_delete=models.CASCADE)
    model = models.CharField(
        max_length=255,
        null=False,
        choices=get_model_choices(),
        help_text="Model to apply validator")
    model_field = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        choices=get_model_field_choices(),
        help_text="Select model and its field"
    )

    class Meta:
        verbose_name = "Standard Validator Assignment"
        verbose_name_plural = "Standard Validator Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=['model', 'model_field', 'validator'], name='unique_model_field_validator')
        ]

    def __str__(self):
        return f'{self.model_field} - {self.validator.name}'

    def clean(self):
        cls = get_class_from_full_path(self.model)
        if not hasattr(cls, self.model_field):
            raise ValidationError({
                'model_field': f'Model "{cls.__name__}" does not have field "{self.model_field}"'
            })


class ClusterDataField(models.Model):
    class Meta:
        verbose_name = 'Cluster Custom Data Field'
        verbose_name_plural = 'Cluster Custom Data Fields'

    name = models.CharField(max_length=64, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ClusterDataFieldValidatorAssignment(models.Model):
    class Meta:
        verbose_name = 'Custom Data Validator Assignment'
        verbose_name_plural = 'Custom Data Validator Assignments'
        constraints = [
            models.UniqueConstraint(fields=['field', 'validator'], name='unique_field_validator')
        ]

    field = models.ForeignKey(ClusterDataField, on_delete=models.DO_NOTHING)
    validator = models.ForeignKey(Validator, on_delete=models.DO_NOTHING)

    def __str__(self):
        return f'Field "{self.field.name}" - Validator "{self.validator.name}"'


class ClusterData(models.Model):
    class Meta:
        verbose_name = 'Cluster Custom Data'
        verbose_name_plural = 'Cluster Custom Data'
        constraints = [
            models.UniqueConstraint(fields=['cluster', 'field'], name='unique_cluster_field')
        ]

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    field = models.ForeignKey(ClusterDataField, on_delete=models.CASCADE)
    value = models.CharField(max_length=1024, null=True, blank=True)

    def __str__(self):
        return f'{self.cluster.name} - "{self.field.name}" = "{self.value}"'

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

        logger.debug(f'Validating {self.__class__.__name__} with parameters: {self.__dict__!r} ')
        super().clean()

        errors = defaultdict(list)
        for va in ClusterDataFieldValidatorAssignment.objects.filter(field=self.field.id):
            Validator = get_class_from_full_path(va.validator.validator)

            try:
                validator = Validator(**va.validator.parameters)
            except TypeError:
                logger.error(
                    f'Invalid parameters for validator '
                    f'{va.validator.name}: {va.validator.parameters}')
                raise

            try:
                validator.validate(self.value)
            except ValidationError as e:
                logger.info("Validation error", e)
                errors['field'].append(e)

        if errors:
            raise ValidationError(errors)
