from rest_framework import serializers

from .models import DetallePedido, Pedido


class DetallePedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetallePedido
        fields = ["id", "producto_id", "nombre_producto", "cantidad", "precio_unitario"]


class PedidoSerializer(serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = [
            "id", "cliente_id", "negocio_id", "repartidor_id", "estado", "total",
            "direccion_entrega", "created_at", "motivo_cancelacion", "detalles",
        ]
        read_only_fields = ["id", "cliente_id", "repartidor_id", "estado", "total", "created_at"]


class ItemCarritoSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


class CrearPedidoSerializer(serializers.Serializer):
    direccion_entrega = serializers.CharField(max_length=255)
    items = ItemCarritoSerializer(many=True)

    def validate_items(self, valor):
        if not valor:
            raise serializers.ValidationError("El carrito no puede estar vacio.")
        return valor
