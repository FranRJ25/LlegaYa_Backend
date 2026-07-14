from django.db import models


class Producto(models.Model):
    CATEGORIAS = [
        ("comida", "Comida"),
        ("bebida", "Bebida"),
        ("postre", "Postre"),
        ("snack", "Snack"),
        ("medicina", "Medicina"),
        ("higiene", "Higiene"),
        ("abarrotes", "Abarrotes"),
        ("otro", "Otro"),
    ]

    negocio_id = models.BigIntegerField()
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default="otro")
    disponible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "producto"

    def __str__(self):
        return self.nombre


class HistorialCambioProducto(models.Model):
    TIPOS = [
        ("creacion", "Creacion"),
        ("precio", "Precio"),
        ("disponible", "Disponible"),
        ("nombre", "Nombre"),
        ("descripcion", "Descripcion"),
        ("categoria", "Categoria"),
        ("eliminacion", "Eliminacion"),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="historial")
    usuario_id = models.BigIntegerField(null=True, blank=True)
    tipo_cambio = models.CharField(max_length=20, choices=TIPOS)
    valor_anterior = models.CharField(max_length=255, blank=True, default="")
    valor_nuevo = models.CharField(max_length=255, blank=True, default="")
    comentario = models.CharField(max_length=255, blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_cambio_producto"
        ordering = ["-fecha"]
