from rest_framework import serializers

from .models import Negocio
from .validators import validar_descripcion, validar_direccion, validar_ruc, validar_telefono_peruano


class NegocioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Negocio
        fields = [
            "id", "propietario_id", "nombre", "descripcion", "direccion", "categoria", "activo",
            "created_at", "ruc", "razon_social", "telefono", "hora_apertura", "hora_cierre",
            "dias_atencion", "comision_porcentaje",
        ]
        read_only_fields = ["id", "propietario_id", "created_at", "comision_porcentaje"]

    def validate_ruc(self, valor):
        validar_ruc(valor)
        return valor

    def validate_telefono(self, valor):
        validar_telefono_peruano(valor)
        return valor

    def validate_descripcion(self, valor):
        validar_descripcion(valor)
        return valor

    def validate_direccion(self, valor):
        validar_direccion(valor)
        return valor
