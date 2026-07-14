from unittest.mock import Mock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .documents import PerfilRepartidor


def token_para(user_id, rol="repartidor"):
    token = AccessToken()
    token["user_id"] = user_id
    token["rol"] = rol
    return str(token)


class RepartidorTestCase(APITestCase):
    def tearDown(self):
        PerfilRepartidor.objects.delete()
        super().tearDown()


class MiPerfilRepartidorTests(RepartidorTestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1)}")

    def test_crear_perfil_repartidor(self):
        url = reverse("repartidores-perfil")
        payload = {"dni": "12345678", "vehiculo": "moto", "zona_cobertura": "Los Olivos"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PerfilRepartidor.objects.count(), 1)
        self.assertEqual(PerfilRepartidor.objects.first().usuario_id, 1)

    def test_no_permite_dos_perfiles_para_el_mismo_usuario(self):
        PerfilRepartidor(usuario_id=1, dni="12345678").save()
        url = reverse("repartidores-perfil")
        response = self.client.post(url, {"dni": "87654321"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_toggle_disponibilidad(self):
        PerfilRepartidor(usuario_id=1, dni="12345678", disponible=True).save()
        url = reverse("repartidores-disponibilidad")
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(PerfilRepartidor.objects.get(usuario_id=1).disponible)


class PedidosDisponiblesTests(RepartidorTestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1)}")

    def test_repartidor_no_disponible_devuelve_lista_vacia(self):
        PerfilRepartidor(usuario_id=1, dni="12345678", disponible=False, zona_cobertura="Los Olivos").save()
        url = reverse("repartidores-pedidos-disponibles")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    @patch("repartidores.views.llamar")
    def test_repartidor_disponible_consulta_pedidos_por_zona(self, mock_llamar):
        PerfilRepartidor(usuario_id=1, dni="12345678", disponible=True, zona_cobertura="Los Olivos").save()
        mock_llamar.return_value = Mock(status_code=200, json=lambda: [{"id": 1, "direccion_entrega": "Los Olivos"}])
        url = reverse("repartidores-pedidos-disponibles")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        args, kwargs = mock_llamar.call_args
        self.assertIn(("palabra", "Olivos"), kwargs["params"])


class TomarPedidoTests(RepartidorTestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1)}")
        PerfilRepartidor(usuario_id=1, dni="12345678", disponible=True).save()

    @patch("repartidores.views.llamar")
    def test_tomar_pedido_llama_a_servicio_pedidos_via_gateway(self, mock_llamar):
        mock_llamar.return_value = Mock(status_code=200, json=lambda: {"id": 7, "estado": "confirmado"})
        url = reverse("repartidores-tomar-pedido", args=[7])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_llamar.assert_called_once()
        args, kwargs = mock_llamar.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertIn("/api/pedidos/7/asignar-repartidor/", args[1])
        self.assertEqual(kwargs["json"], {"repartidor_id": 1})
