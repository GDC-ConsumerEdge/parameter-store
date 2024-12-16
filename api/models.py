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
            ("can_get_params_api", "Can get from params API endpoints"),
        ]
