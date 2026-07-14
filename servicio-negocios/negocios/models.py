from decimal import Decimal

from django.db import models


class Negocio(models.Model):
    CATEGORIAS = [
        ("restaurante", "Restaurante"),
        ("tienda", "Tienda"),
        ("farmacia", "Farmacia"),
        ("bodega", "Bodega"),
        ("mercado", "Mercado"),
        ("postres", "Postres"),
        ("otro", "Otro"),
    ]

    propietario_id = models.BigIntegerField(unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    direccion = models.CharField(max_length=255)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default="otro")
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    ruc = models.CharField(max_length=11, blank=True)
    razon_social = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=9, blank=True)
    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)
    dias_atencion = models.JSONField(default=list, blank=True)
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))

    class Meta:
        db_table = "negocio"

    def __str__(self):
        return self.nombre
