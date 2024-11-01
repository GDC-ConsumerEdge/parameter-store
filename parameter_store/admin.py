from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered

app = apps.get_app_config('parameter_store')

for model_name, model in app.models.items():
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        pass
