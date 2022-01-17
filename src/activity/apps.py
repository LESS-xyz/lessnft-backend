from django.apps import AppConfig


class ActivityConfig(AppConfig):
    name = "src.activity"

    def ready(self):
        from . import signals
