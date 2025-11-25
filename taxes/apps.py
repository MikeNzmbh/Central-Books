from django.apps import AppConfig


class TaxesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "taxes"

    def ready(self):
        # Import signal handlers to seed defaults on business creation.
        from . import signals  # noqa: F401
