"""
PRUEBAS UNITARIAS — LlegaYa Backend (Django + DRF)
====================================================
Archivo: apps/security/tests.py
Ejecutar con:
    python manage.py test apps.security
Requiere que las migraciones estén aplicadas y la BD de test disponible.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from unittest.mock import patch, MagicMock

from .models import Rol, Usuario, Negocio, Producto, Pedido
from .serializers import (
    RegisterSerializer,
    RegisterRepartidorSerializer,
    NegocioSerializer,
    ProductoSerializer,
)
from .permissions import (
    EsAdmin,
    EsCliente,
    EsRepartidor,
    EsPropietarioDeNegocio,
    EsAdminORepartidor,
)

Usuario = get_user_model()


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def crear_rol(nombre):
    rol, _ = Rol.objects.get_or_create(nombre=nombre)
    return rol


def crear_usuario(email, password='Test1234!', rol_nombre='cliente', **kwargs):
    rol = crear_rol(rol_nombre)
    return Usuario.objects.create_user(
        email=email,
        password=password,
        nombre=kwargs.get('nombre', 'Test'),
        apellido=kwargs.get('apellido', 'User'),
        rol=rol,
    )


# ─────────────────────────────────────────────────────────────────
# 1. MODELO — Rol
# ─────────────────────────────────────────────────────────────────

class RolModelTest(TestCase):

    def test_crear_rol_valido(self):
        """Se puede crear un Rol con nombre válido."""
        rol = Rol.objects.create(nombre='admin')
        self.assertEqual(str(rol), 'admin')

    def test_rol_nombre_unico(self):
        """No se pueden crear dos roles con el mismo nombre."""
        from django.db import IntegrityError
        Rol.objects.create(nombre='cliente')
        with self.assertRaises(IntegrityError):
            Rol.objects.create(nombre='cliente')


# ─────────────────────────────────────────────────────────────────
# 2. MODELO — UsuarioManager
# ─────────────────────────────────────────────────────────────────

class UsuarioManagerTest(TestCase):

    def test_create_user_requiere_email(self):
        """create_user lanza ValueError si no se provee email."""
        with self.assertRaises(ValueError):
            Usuario.objects.create_user(email='', password='pass')

    def test_create_user_normaliza_email(self):
        """El email se normaliza a minúsculas en el dominio."""
        user = Usuario.objects.create_user(
            email='Test@EXAMPLE.COM', password='pass', nombre='A', apellido='B'
        )
        self.assertEqual(user.email, 'Test@example.com')

    def test_create_superuser_tiene_flags(self):
        """create_superuser activa is_staff e is_superuser."""
        su = Usuario.objects.create_superuser(
            email='admin@test.com', password='pass', nombre='A', apellido='B'
        )
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)


# ─────────────────────────────────────────────────────────────────
# 3. PERMISSIONS
# ─────────────────────────────────────────────────────────────────

class PermissionsTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    def _request_con_usuario(self, rol_nombre):
        request = self.factory.get('/')
        request.user = crear_usuario(f'{rol_nombre}@test.com', rol_nombre=rol_nombre)
        return request

    # EsAdmin
    def test_es_admin_permite_admin(self):
        request = self._request_con_usuario('admin')
        self.assertTrue(EsAdmin().has_permission(request, None))

    def test_es_admin_rechaza_cliente(self):
        request = self._request_con_usuario('cliente')
        self.assertFalse(EsAdmin().has_permission(request, None))

    # EsCliente
    def test_es_cliente_permite_cliente(self):
        request = self._request_con_usuario('cliente')
        self.assertTrue(EsCliente().has_permission(request, None))

    def test_es_cliente_rechaza_admin(self):
        request = self._request_con_usuario('admin')
        self.assertFalse(EsCliente().has_permission(request, None))

    # EsRepartidor
    def test_es_repartidor_permite_repartidor(self):
        request = self._request_con_usuario('repartidor')
        self.assertTrue(EsRepartidor().has_permission(request, None))

    # EsAdminORepartidor
    def test_es_admin_o_repartidor_permite_admin(self):
        request = self._request_con_usuario('admin')
        self.assertTrue(EsAdminORepartidor().has_permission(request, None))

    def test_es_admin_o_repartidor_permite_repartidor(self):
        request = self._request_con_usuario('repartidor')
        self.assertTrue(EsAdminORepartidor().has_permission(request, None))

    def test_es_admin_o_repartidor_rechaza_cliente(self):
        request = self._request_con_usuario('cliente')
        self.assertFalse(EsAdminORepartidor().has_permission(request, None))

    # EsPropietarioDeNegocio
    def test_propietario_negocio_sin_negocio_es_rechazado(self):
        request = self.factory.get('/')
        request.user = crear_usuario('sinNegocio@test.com', rol_nombre='cliente')
        self.assertFalse(EsPropietarioDeNegocio().has_permission(request, None))

    def test_propietario_negocio_con_negocio_es_permitido(self):
        request = self.factory.get('/')
        usuario = crear_usuario('conNegocio@test.com', rol_nombre='cliente')
        Negocio.objects.create(
            propietario=usuario,
            nombre='Mi Tienda',
            direccion='Calle 1',
        )
        request.user = usuario
        self.assertTrue(EsPropietarioDeNegocio().has_permission(request, None))

    # Usuario anónimo
    def test_usuario_anonimo_rechazado_en_todos(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get('/')
        request.user = AnonymousUser()
        for PermClass in [EsAdmin, EsCliente, EsRepartidor, EsAdminORepartidor, EsPropietarioDeNegocio]:
            with self.subTest(permiso=PermClass.__name__):
                self.assertFalse(PermClass().has_permission(request, None))


# ─────────────────────────────────────────────────────────────────
# 4. SERIALIZERS
# ─────────────────────────────────────────────────────────────────

class RegisterSerializerTest(TestCase):

    def setUp(self):
        crear_rol('cliente')

    def _payload_valido(self, email='nuevo@test.com'):
        return {
            'email': email,
            'password': 'Segura123!',
            'nombre': 'Juan',
            'apellido': 'Pérez',
            'telefono': '987654321',
        }

    def test_registro_valido_crea_usuario(self):
        serializer = RegisterSerializer(data=self._payload_valido())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        usuario = serializer.save()
        self.assertEqual(usuario.email, 'nuevo@test.com')

    def test_registro_email_duplicado_falla(self):
        crear_usuario('duplicado@test.com')
        serializer = RegisterSerializer(data=self._payload_valido(email='duplicado@test.com'))
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_registro_sin_email_falla(self):
        payload = self._payload_valido()
        payload.pop('email')
        serializer = RegisterSerializer(data=payload)
        self.assertFalse(serializer.is_valid())


class RegisterRepartidorSerializerTest(TestCase):

    def setUp(self):
        crear_rol('repartidor')

    def _payload_valido(self):
        return {
            'nombres': 'Carlos',
            'apellidos': 'Ríos',
            'email': 'repartidor@test.com',
            'celular': '999000111',
            'password': 'Segura123!',
            'vehiculo': 'moto',
            'zona_cobertura': 'Miraflores',
        }

    def test_repartidor_valido_se_crea(self):
        serializer = RegisterRepartidorSerializer(data=self._payload_valido())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        usuario = serializer.save()
        self.assertEqual(usuario.email, 'repartidor@test.com')
        self.assertEqual(usuario.rol.nombre, 'repartidor')

    def test_email_duplicado_falla(self):
        crear_usuario('repartidor@test.com', rol_nombre='repartidor')
        serializer = RegisterRepartidorSerializer(data=self._payload_valido())
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_vehiculo_invalido_falla(self):
        payload = self._payload_valido()
        payload['vehiculo'] = 'helicoptero'
        serializer = RegisterRepartidorSerializer(data=payload)
        self.assertFalse(serializer.is_valid())


class NegocioSerializerTest(TestCase):

    def test_negocio_requiere_nombre(self):
        serializer = NegocioSerializer(data={'descripcion': 'Sin nombre'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('nombre', serializer.errors)


# ─────────────────────────────────────────────────────────────────
# 5. ENDPOINTS — Autenticación (APITestCase)
# ─────────────────────────────────────────────────────────────────

class AuthEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.url_registro = '/api/auth/register/'
        self.url_login    = '/api/auth/login/'

    def test_registro_crea_usuario_201(self):
        payload = {
            'email': 'user@test.com',
            'password': 'Segura123!',
            'nombre': 'Ana',
            'apellido': 'García',
        }
        response = self.client.post(self.url_registro, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_login_credenciales_incorrectas_retorna_401(self):
        payload = {'email': 'noexiste@test.com', 'password': 'wrong'}
        response = self.client.post(self.url_login, payload, format='json')
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
        ])

    def test_ruta_protegida_sin_token_retorna_401(self):
        response = self.client.get('/api/auth/perfil/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────
# 6. ENDPOINT — Registro Repartidor
# ─────────────────────────────────────────────────────────────────

class RegisterRepartidorEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('repartidor')
        self.url = '/api/auth/repartidor/register/'

    def _payload(self, email='rep@test.com'):
        return {
            'nombres': 'Luis',
            'apellidos': 'Torres',
            'email': email,
            'celular': '900000001',
            'password': 'Segura123!',
            'vehiculo': 'bicicleta',
            'zona_cobertura': 'Surco',
        }

    def test_registro_exitoso_retorna_201(self):
        response = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_datos_incompletos_retorna_400(self):
        response = self.client.post(self.url, {'email': 'x@x.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────
# 7. MODELO — Negocio
# ─────────────────────────────────────────────────────────────────

class NegocioModelTest(TestCase):

    def test_negocio_se_crea_con_propietario(self):
        usuario = crear_usuario('owner@test.com', rol_nombre='cliente')
        negocio = Negocio.objects.create(
            propietario=usuario,
            nombre='Pollería El Sol',
            direccion='Av. Principal 123',
            categoria='restaurante',
        )
        self.assertEqual(negocio.nombre, 'Pollería El Sol')
        self.assertEqual(negocio.propietario, usuario)

    def test_negocio_activo_por_defecto(self):
        usuario = crear_usuario('owner2@test.com', rol_nombre='cliente')
        negocio = Negocio.objects.create(
            propietario=usuario,
            nombre='Farmacia',
            direccion='Jr. Lima 5',
        )
        self.assertTrue(negocio.activo)


# ─────────────────────────────────────────────────────────────────
# 8. MODELO — Producto
# ─────────────────────────────────────────────────────────────────

class ProductoModelTest(TestCase):

    def setUp(self):
        usuario = crear_usuario('prod_owner@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=usuario,
            nombre='Mi Tienda',
            direccion='Calle 10',
        )

    def test_producto_se_crea_con_datos_validos(self):
        producto = Producto.objects.create(
            negocio=self.negocio,
            nombre='Pollo a la brasa',
            precio=35.50,
            disponible=True,
        )
        self.assertEqual(str(producto.precio), '35.5')
        self.assertTrue(producto.disponible)

    def test_producto_disponible_por_defecto(self):
        producto = Producto.objects.create(
            negocio=self.negocio,
            nombre='Arroz con leche',
            precio=5.00,
        )
        self.assertTrue(producto.disponible)
