from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Negocio


def token_para(user_id, rol="cliente", email="test@test.com"):
    token = AccessToken()
    token["user_id"] = user_id
    token["rol"] = rol
    token["email"] = email
    return str(token)


class MiNegocioTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_para(1, rol='cliente')}")

    def test_crear_negocio_propio(self):
        url = reverse("negocios-mi-negocio")
        payload = {
            "nombre": "Bodega Ana",
            "descripcion": "Abarrotes",
            "direccion": "Av. Siempre Viva 123",
            "categoria": "bodega",
            "ruc": "12345678901",
            "telefono": "912345678",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Negocio.objects.get().propietario_id, 1)

    def test_no_permite_dos_negocios_para_el_mismo_propietario(self):
        Negocio.objects.create(propietario_id=1, nombre="Uno", direccion="Calle 1")
        url = reverse("negocios-mi-negocio")
        response = self.client.post(url, {"nombre": "Dos", "direccion": "Calle 2"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sin_token_devuelve_401(self):
        self.client.credentials()
        url = reverse("negocios-mi-negocio")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ListaNegociosTests(APITestCase):
    def test_lista_solo_negocios_activos(self):
        Negocio.objects.create(propietario_id=1, nombre="Activo", direccion="Calle 1", activo=True)
        Negocio.objects.create(propietario_id=2, nombre="Inactivo", direccion="Calle 2", activo=False)
        url = reverse("negocios-lista")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["nombre"], "Activo")
