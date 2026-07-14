from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Pedido


def token_para(user_id, rol="cliente"):
    token = AccessToken()
    token["user_id"] = user_id
    token["rol"] = rol
    return str(token)


PRODUCTO_A = {"id": 1, "negocio_id": 10, "nombre": "Chaufa", "precio": "18.50", "disponible": True}
PRODUCTO_B = {"id": 2, "negocio_id": 20, "nombre": "Gaseosa", "precio": "5.00", "disponible": True}


class CrearPedidoTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1, rol='cliente')}")

    @patch("pedidos.views.obtener_producto")
    def test_crea_un_pedido_por_negocio_agrupando_el_carrito(self, mock_obtener_producto):
        mock_obtener_producto.side_effect = lambda pid, _h: {1: PRODUCTO_A, 2: PRODUCTO_B}[pid]

        url = reverse("pedidos-crear")
        payload = {
            "direccion_entrega": "Av. Siempre Viva 123",
            "items": [{"producto_id": 1, "cantidad": 2}, {"producto_id": 2, "cantidad": 3}],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pedido.objects.count(), 2)

        pedido_a = Pedido.objects.get(negocio_id=10)
        self.assertEqual(pedido_a.total, Decimal("37.00"))
        pedido_b = Pedido.objects.get(negocio_id=20)
        self.assertEqual(pedido_b.total, Decimal("15.00"))

    @patch("pedidos.views.obtener_producto")
    def test_falla_si_un_producto_no_esta_disponible(self, mock_obtener_producto):
        mock_obtener_producto.return_value = {**PRODUCTO_A, "disponible": False}
        url = reverse("pedidos-crear")
        payload = {"direccion_entrega": "Calle 1", "items": [{"producto_id": 1, "cantidad": 1}]}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pedido.objects.count(), 0)


class CancelarCompletarPedidoTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1, rol='cliente')}")

    def test_cancelar_pedido_pendiente(self):
        pedido = Pedido.objects.create(cliente_id=1, negocio_id=10, direccion_entrega="Calle 1")
        url = reverse("pedidos-cancelar", args=[pedido.id])
        response = self.client.post(url, {"motivo_cancelacion": "Ya no lo quiero"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "cancelado")

    def test_no_cancela_pedido_ya_confirmado(self):
        pedido = Pedido.objects.create(cliente_id=1, negocio_id=10, direccion_entrega="Calle 1", estado="confirmado")
        url = reverse("pedidos-cancelar", args=[pedido.id])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AsignarRepartidorTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(2, rol='repartidor')}")

    def test_asigna_repartidor_a_pedido_pendiente(self):
        pedido = Pedido.objects.create(cliente_id=1, negocio_id=10, direccion_entrega="Calle 1")
        url = reverse("pedidos-asignar-repartidor", args=[pedido.id])
        response = self.client.patch(url, {"repartidor_id": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pedido.refresh_from_db()
        self.assertEqual(pedido.repartidor_id, 2)
        self.assertEqual(pedido.estado, "confirmado")

    def test_no_permite_doble_asignacion(self):
        pedido = Pedido.objects.create(
            cliente_id=1, negocio_id=10, direccion_entrega="Calle 1", estado="confirmado", repartidor_id=5
        )
        url = reverse("pedidos-asignar-repartidor", args=[pedido.id])
        response = self.client.patch(url, {"repartidor_id": 2}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_disponibles_filtra_por_palabras_de_direccion(self):
        Pedido.objects.create(cliente_id=1, negocio_id=10, direccion_entrega="Av. Los Olivos 123")
        Pedido.objects.create(cliente_id=1, negocio_id=10, direccion_entrega="Jr. Otro Lugar 456")
        url = reverse("pedidos-disponibles")
        response = self.client.get(url, {"palabra": "olivos"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
