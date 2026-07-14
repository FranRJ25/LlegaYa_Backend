from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import HistorialCambioProducto, Producto


def token_para(user_id, rol="cliente"):
    token = AccessToken()
    token["user_id"] = user_id
    token["rol"] = rol
    return str(token)


class ProductoTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1, rol='cliente')}")

    @patch("productos.views.obtener_negocio")
    def test_crear_producto_registra_historial_de_creacion(self, mock_obtener_negocio):
        mock_obtener_negocio.return_value = {"id": 5, "propietario_id": 1}
        url = reverse("productos-crear")
        payload = {"negocio_id": 5, "nombre": "Chaufa", "precio": "18.50", "categoria": "comida"}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        producto = Producto.objects.get()
        self.assertEqual(producto.negocio_id, 5)
        self.assertEqual(HistorialCambioProducto.objects.filter(tipo_cambio="creacion").count(), 1)

    @patch("productos.views.obtener_negocio")
    def test_crear_producto_falla_si_no_es_propietario(self, mock_obtener_negocio):
        mock_obtener_negocio.return_value = {"id": 5, "propietario_id": 99}
        url = reverse("productos-crear")
        response = self.client.post(url, {"negocio_id": 5, "nombre": "Chaufa", "precio": "18.50"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("productos.views.obtener_negocio")
    def test_toggle_disponibilidad_registra_historial(self, mock_obtener_negocio):
        mock_obtener_negocio.return_value = {"id": 5, "propietario_id": 1}
        producto = Producto.objects.create(negocio_id=5, nombre="Chaufa", precio=Decimal("18.50"))
        url = reverse("productos-toggle", args=[producto.id])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        producto.refresh_from_db()
        self.assertFalse(producto.disponible)
        self.assertEqual(HistorialCambioProducto.objects.filter(tipo_cambio="disponible").count(), 1)

    @patch("productos.views.obtener_negocio")
    def test_actualizar_precio_solo_registra_historial_si_cambia(self, mock_obtener_negocio):
        mock_obtener_negocio.return_value = {"id": 5, "propietario_id": 1}
        producto = Producto.objects.create(negocio_id=5, nombre="Chaufa", precio=Decimal("18.50"))
        url = reverse("productos-precio", args=[producto.id])

        response = self.client.patch(url, {"precio": "18.50"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(HistorialCambioProducto.objects.filter(tipo_cambio="precio").count(), 0)

        response = self.client.patch(url, {"precio": "20.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(HistorialCambioProducto.objects.filter(tipo_cambio="precio").count(), 1)

    def test_lista_productos_es_publica(self):
        self.client.credentials()
        Producto.objects.create(negocio_id=5, nombre="Chaufa", precio=Decimal("18.50"))
        url = reverse("productos-lista")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
