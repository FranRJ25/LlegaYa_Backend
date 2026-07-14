from django.urls import path

from .views import (
    AsignarRepartidorView,
    CancelarPedidoView,
    CompletarPedidoView,
    CrearPedidoView,
    DetallePedidoView,
    ListaMisPedidosView,
    PedidosDisponiblesView,
)

urlpatterns = [
    path("crear/", CrearPedidoView.as_view(), name="pedidos-crear"),
    path("mis-pedidos/", ListaMisPedidosView.as_view(), name="pedidos-mis-pedidos"),
    path("disponibles/", PedidosDisponiblesView.as_view(), name="pedidos-disponibles"),
    path("<int:pk>/", DetallePedidoView.as_view(), name="pedidos-detalle"),
    path("<int:pk>/cancelar/", CancelarPedidoView.as_view(), name="pedidos-cancelar"),
    path("<int:pk>/completar/", CompletarPedidoView.as_view(), name="pedidos-completar"),
    path("<int:pk>/asignar-repartidor/", AsignarRepartidorView.as_view(), name="pedidos-asignar-repartidor"),
]
