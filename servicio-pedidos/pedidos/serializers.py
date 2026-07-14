from rest_framework import serializers

from .models import Calificacion, DetallePedido, Incidencia, Pago, Pedido


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


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = [
            "id", "pedido", "monto", "metodo", "numero_transaccion", "fecha",
            "comision_plataforma", "monto_comercio", "monto_repartidor",
        ]
        read_only_fields = fields


class PedidoConPagoSerializer(PedidoSerializer):
    pago = serializers.SerializerMethodField()

    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + ["pago"]

    def get_pago(self, obj):
        try:
            return PagoSerializer(obj.pago).data
        except Pago.DoesNotExist:
            return None


class HistorialPagoSerializer(serializers.ModelSerializer):
    """HU15 - una fila del historial de pagos, con la distribucion calculada en HU14."""

    monto_total = serializers.DecimalField(source="monto", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id", "pedido", "fecha", "metodo", "monto_total",
            "comision_plataforma", "monto_comercio", "monto_repartidor",
        ]
        read_only_fields = fields


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = ["id", "pedido", "repartidor_id", "estrellas", "comentario", "fecha"]
        read_only_fields = ["id", "pedido", "repartidor_id", "fecha"]

    def validate_estrellas(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Las estrellas deben estar entre 1 y 5.")
        return value


class IncidenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incidencia
        fields = [
            "id", "pedido", "cliente_id", "tipo", "descripcion", "estado", "respuesta",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "pedido", "cliente_id", "estado", "respuesta", "created_at", "updated_at"]


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
