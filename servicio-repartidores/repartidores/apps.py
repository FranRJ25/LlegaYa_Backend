import sys

import mongoengine
from django.apps import AppConfig
from django.conf import settings

COMANDOS_SIN_ARRANQUE = {"migrate", "makemigrations", "test", "collectstatic", "shell", "createsuperuser"}


class RepartidoresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "repartidores"

    def ready(self):
        if getattr(settings, "USA_MONGOMOCK", False):
            import mongomock

            mongoengine.connect(host=settings.MONGO_URI, mongo_client_class=mongomock.MongoClient)
        else:
            mongoengine.connect(host=settings.MONGO_URI)

        if any(cmd in sys.argv for cmd in COMANDOS_SIN_ARRANQUE):
            return

        from core import config_cliente, registro_cliente

        config_cliente.obtener_config()
        registro_cliente.iniciar()
