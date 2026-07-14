from datetime import datetime, timezone

import mongoengine as me

VEHICULOS = ("moto", "bicicleta", "a_pie", "auto")


class PerfilRepartidor(me.Document):
    usuario_id = me.IntField(required=True, unique=True)
    dni = me.StringField(required=True, max_length=8)
    vehiculo = me.StringField(choices=VEHICULOS, default="moto")
    zona_cobertura = me.StringField(default="")
    disponible = me.BooleanField(default=True)
    created_at = me.DateTimeField(default=lambda: datetime.now(timezone.utc))

    meta = {"collection": "perfil_repartidor"}
