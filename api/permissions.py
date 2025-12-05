from django.db import models


class CustomAPIPermissions(models.Model):
    """
    Abstract model to define API permissions.
    This doesn't create a database table but provides a Django-like way to define permissions.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # Global Permissions
            ("params_api_create_objects", "Can create any object via API"),
            ("params_api_read_objects", "Can read any object via API"),
            ("params_api_update_objects", "Can update any object via API"),
            ("params_api_delete_objects", "Can delete any object via API"),
            # ChangeSet Permissions
            ("params_api_create_changeset", "Can create ChangeSet via API"),
            ("params_api_read_changeset", "Can read ChangeSet via API"),
            ("params_api_update_changeset", "Can update ChangeSet via API"),
            ("params_api_delete_changeset", "Can delete ChangeSet via API"),
            # Group Permissions
            ("params_api_create_group", "Can create Group via API"),
            ("params_api_read_group", "Can read Group via API"),
            ("params_api_update_group", "Can update Group via API"),
            ("params_api_delete_group", "Can delete Group via API"),
            # Cluster Permissions
            ("params_api_create_cluster", "Can create Cluster via API"),
            ("params_api_read_cluster", "Can read Cluster via API"),
            ("params_api_update_cluster", "Can update Cluster via API"),
            ("params_api_delete_cluster", "Can delete Cluster via API"),
            # Tag Permissions
            ("params_api_create_tag", "Can create Tag via API"),
            ("params_api_read_tag", "Can read Tag via API"),
            ("params_api_update_tag", "Can update Tag via API"),
            ("params_api_delete_tag", "Can delete Tag via API"),
        ]
