from django.urls import path

from .views import (
    MiPerfilRepartidorView,
    PedidosDisponiblesView,
    PromedioCalificacionesRepartidorView,
    ToggleDisponibilidadRepartidorView,
    TomarPedidoView,
)

urlpatterns = [
    path("perfil/", MiPerfilRepartidorView.as_view(), name="repartidores-perfil"),
    path("perfil/disponibilidad/", ToggleDisponibilidadRepartidorView.as_view(), name="repartidores-disponibilidad"),
    path("pedidos-disponibles/", PedidosDisponiblesView.as_view(), name="repartidores-pedidos-disponibles"),
    path("pedidos/<int:pedido_id>/tomar/", TomarPedidoView.as_view(), name="repartidores-tomar-pedido"),
    path("calificaciones/promedio/", PromedioCalificacionesRepartidorView.as_view(), name="repartidores-calificaciones-promedio"),
]
