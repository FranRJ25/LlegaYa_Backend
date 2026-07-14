import re

from rest_framework import serializers

from .documents import VEHICULOS


def validar_dni(valor):
    if not re.match(r"^\d{8}$", valor or ""):
        raise serializers.ValidationError("El DNI debe tener 8 digitos.")


class PerfilRepartidorSerializer(serializers.Serializer):
    """Serializer plano (no ModelSerializer): PerfilRepartidor es un mongoengine.Document,
    no un modelo de Django."""

    id = serializers.CharField(read_only=True)
    usuario_id = serializers.IntegerField(read_only=True)
    dni = serializers.CharField(max_length=8, validators=[validar_dni])
    vehiculo = serializers.ChoiceField(choices=VEHICULOS, default="moto")
    zona_cobertura = serializers.CharField(max_length=255, required=False, allow_blank=True)
    disponible = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "usuario_id": instance.usuario_id,
            "dni": instance.dni,
            "vehiculo": instance.vehiculo,
            "zona_cobertura": instance.zona_cobertura,
            "disponible": instance.disponible,
            "created_at": instance.created_at.isoformat() if instance.created_at else None,
        }
