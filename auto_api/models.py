from django.db import models


# Create your models here.
class ExampleModel(models.Model):
    pass

    def __str__(self):
        return self.name