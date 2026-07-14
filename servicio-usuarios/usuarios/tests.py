from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PasswordResetToken, Rol, Usuario


class RegistroLoginTests(APITestCase):
    def test_registro_crea_usuario_con_rol_cliente_por_defecto(self):
        url = reverse("usuarios-register")
        payload = {
            "email": "cliente@test.com",
            "password": "Clave1234",
            "nombre": "Ana",
            "apellido": "Perez",
            "telefono": "912345678",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        usuario = Usuario.objects.get(email="cliente@test.com")
        self.assertEqual(usuario.rol.nombre, Rol.CLIENTE)

    def test_login_devuelve_access_token_y_cookie_refresh(self):
        Usuario.objects.create_user(email="a@test.com", password="Clave1234", nombre="Ana")
        url = reverse("usuarios-login")
        response = self.client.post(url, {"email": "a@test.com", "password": "Clave1234"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh_token", response.cookies)

    def test_ruta_protegida_sin_token_devuelve_401(self):
        url = reverse("usuarios-perfil")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email="reset@test.com", password="Clave1234", nombre="Ana")

    def test_solicitud_reset_siempre_devuelve_200(self):
        url = reverse("usuarios-password-reset-request")
        response = self.client.post(url, {"email": "no-existe@test.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_confirmar_reset_con_token_valido_cambia_password(self):
        token = PasswordResetToken.objects.create(user=self.usuario)
        url = reverse("usuarios-password-reset-confirm")
        response = self.client.post(url, {"token": str(token.token), "password": "NuevaClave1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NuevaClave1"))

    def test_confirmar_reset_con_token_usado_falla(self):
        token = PasswordResetToken.objects.create(user=self.usuario, used=True)
        url = reverse("usuarios-password-reset-confirm")
        response = self.client.post(url, {"token": str(token.token), "password": "NuevaClave1"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
