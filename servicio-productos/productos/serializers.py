from rest_framework import serializers

from .models import HistorialCambioProducto, Producto


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = [
            "id", "negocio_id", "nombre", "descripcion", "precio", "categoria",
            "disponible", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "negocio_id", "created_at", "updated_at"]


class HistorialCambioProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorialCambioProducto
        fields = ["id", "producto", "usuario_id", "tipo_cambio", "valor_anterior", "valor_nuevo", "comentario", "fecha"]
