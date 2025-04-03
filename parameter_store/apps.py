from django.apps import AppConfig


class ParamStoreAppConfig(AppConfig):
    name = 'parameter_store'
    verbose_name = 'Parameter Store'

    def ready(self):
        # import signals to register them in the app
        from . import signals  # noqa
