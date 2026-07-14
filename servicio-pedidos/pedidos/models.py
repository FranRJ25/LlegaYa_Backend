from django.db import models


class Pedido(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("confirmado", "Confirmado"),
        ("en_camino", "En camino"),
        ("entregado", "Entregado"),
        ("cancelado", "Cancelado"),
        ("completado", "Completado"),
    ]

    cliente_id = models.BigIntegerField()
    negocio_id = models.BigIntegerField()
    repartidor_id = models.BigIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    direccion_entrega = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    motivo_cancelacion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "pedido"

    def __str__(self):
        return f"Pedido #{self.id} ({self.estado})"


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    producto_id = models.BigIntegerField()
    nombre_producto = models.CharField(max_length=150, blank=True)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        db_table = "detalle_pedido"
