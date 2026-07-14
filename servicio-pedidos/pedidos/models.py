import uuid
from decimal import Decimal

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


class Pago(models.Model):
    METODOS = [
        ("tarjeta", "Tarjeta de credito/debito"),
        ("yape", "Yape"),
        ("plin", "Plin"),
    ]

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name="pago")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODOS, default="tarjeta")
    numero_transaccion = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    fecha = models.DateTimeField(auto_now_add=True)

    comision_plataforma = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    monto_comercio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    monto_repartidor = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "pago"

    def __str__(self):
        return f"Pago #{self.numero_transaccion} - Pedido #{self.pedido_id}"


class Calificacion(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name="calificacion")
    repartidor_id = models.BigIntegerField()
    estrellas = models.PositiveSmallIntegerField()
    comentario = models.TextField(blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calificacion"

    def __str__(self):
        return f"Calificacion #{self.id} - Pedido #{self.pedido_id} - {self.estrellas} estrellas"


class Incidencia(models.Model):
    TIPOS = [
        ("pedido_no_llego", "El pedido no llego"),
        ("pedido_incompleto", "Pedido incompleto"),
        ("producto_danado", "Producto danado"),
        ("repartidor_problema", "Problema con el repartidor"),
        ("cobro_incorrecto", "Cobro incorrecto"),
        ("otro", "Otro"),
    ]
    ESTADOS = [
        ("abierto", "Abierto"),
        ("en_proceso", "En proceso"),
        ("resuelto", "Resuelto"),
        ("rechazado", "Rechazado"),
    ]
    ESTADOS_ACTIVOS = ("abierto", "en_proceso")

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="incidencias")
    cliente_id = models.BigIntegerField()
    tipo = models.CharField(max_length=30, choices=TIPOS)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default="abierto")
    respuesta = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "incidencia"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Incidencia #{self.id} - Pedido #{self.pedido_id} - {self.estado}"
