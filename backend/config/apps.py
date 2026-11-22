from django.apps import AppConfig


class ProjectConfig(AppConfig):
    """The project wiring as an app, so Django loads its system checks."""

    name = "config"

    def ready(self):
        from . import checks  # noqa: F401
