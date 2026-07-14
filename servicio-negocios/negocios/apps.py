import sys

from django.apps import AppConfig

COMANDOS_SIN_ARRANQUE = {"migrate", "makemigrations", "test", "collectstatic", "shell", "createsuperuser"}


class NegociosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "negocios"

    def ready(self):
        if any(cmd in sys.argv for cmd in COMANDOS_SIN_ARRANQUE):
            return

        from core import config_cliente, registro_cliente

        config_cliente.obtener_config()
        registro_cliente.iniciar()
