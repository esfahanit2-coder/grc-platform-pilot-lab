from django.apps import AppConfig


class FrameworksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.frameworks"
    verbose_name = "Framework Management"

    def ready(self):
        from . import signals  # noqa: F401
