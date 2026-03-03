# core/apps.py
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'core'

    def ready(self):
        from .supertokens_config import init_supertokens
        init_supertokens()