from django.urls import path

from .views import (
    ActualizarPrecioProductoView,
    CrearProductoView,
    DetalleProductoView,
    HistorialProductoView,
    ListaProductosView,
    ToggleDisponibilidadProductoView,
)

urlpatterns = [
    path("", ListaProductosView.as_view(), name="productos-lista"),
    path("crear/", CrearProductoView.as_view(), name="productos-crear"),
    path("<int:pk>/", DetalleProductoView.as_view(), name="productos-detalle"),
    path("<int:pk>/toggle-disponibilidad/", ToggleDisponibilidadProductoView.as_view(), name="productos-toggle"),
    path("<int:pk>/actualizar-precio/", ActualizarPrecioProductoView.as_view(), name="productos-precio"),
    path("<int:pk>/historial/", HistorialProductoView.as_view(), name="productos-historial"),
]
