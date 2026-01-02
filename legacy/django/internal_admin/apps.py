from django.apps import AppConfig


class InternalAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "internal_admin"
    verbose_name = "Internal Admin"
