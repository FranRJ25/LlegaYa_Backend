"""
PRUEBAS UNITARIAS — LlegaYa Backend (Django + DRF)
====================================================
Archivo: apps/security/tests.py
Ejecutar con:
    python manage.py test apps.security
Requiere que las migraciones estén aplicadas y la BD de test disponible.
"""

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from unittest.mock import patch, MagicMock

from .models import Rol, Usuario, Negocio, Producto, Pedido, Calificacion, Pago, Incidencia, DetallePedido, PerfilRepartidor
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
            'telefono': '999000111',
            'password': 'Segura123!',
            'dni': '12345678',
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
            'telefono': '987654321',
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
            'telefono': '900000001',
            'password': 'Segura123!',
            'dni': '87654321',
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


# ─────────────────────────────────────────────────────────────────
# 9. ENDPOINTS — Calificaciones (Incidencias 1 y 3)
# ─────────────────────────────────────────────────────────────────

class CalificacionEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        crear_rol('repartidor')

        self.cliente = crear_usuario('cliente_calif@test.com', rol_nombre='cliente')
        self.otro_cliente = crear_usuario('otro_cliente@test.com', rol_nombre='cliente')
        self.repartidor = crear_usuario('repartidor_calif@test.com', rol_nombre='repartidor')

        self.negocio_owner = crear_usuario('negocio_owner_calif@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner,
            nombre='Restaurante Test',
            direccion='Av. Test 123',
        )

        self.pedido_entregado = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            repartidor=self.repartidor,
            estado='entregado',
            total=25.00,
            direccion_entrega='Calle Falsa 123',
        )

        self.pedido_pendiente = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            repartidor=self.repartidor,
            estado='pendiente',
            total=15.00,
            direccion_entrega='Calle Falsa 456',
        )

    def _url_calificar(self, pk):
        return f'/api/auth/pedidos/{pk}/calificar/'

    def _url_calificacion(self, pk):
        return f'/api/auth/pedidos/{pk}/calificacion/'

    def test_calificar_pedido_entregado_retorna_201(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url_calificar(self.pedido_entregado.id),
            {'estrellas': 5, 'comentario': 'Excelente servicio'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Calificacion.objects.filter(pedido=self.pedido_entregado).exists()
        )

    def test_calificar_pedido_ya_calificado_retorna_400(self):
        Calificacion.objects.create(
            pedido=self.pedido_entregado, repartidor=self.repartidor, estrellas=4
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url_calificar(self.pedido_entregado.id),
            {'estrellas': 5, 'comentario': 'Otra vez'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calificar_pedido_no_entregado_retorna_400(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url_calificar(self.pedido_pendiente.id),
            {'estrellas': 3},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calificar_pedido_ajeno_retorna_403(self):
        self.client.force_authenticate(user=self.otro_cliente)
        response = self.client.post(
            self._url_calificar(self.pedido_entregado.id),
            {'estrellas': 5},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_calificar_pedido_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url_calificar(999999),
            {'estrellas': 5},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_calificar_estrellas_invalidas_retorna_400(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url_calificar(self.pedido_entregado.id),
            {'estrellas': 8},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_obtener_calificacion_existente(self):
        Calificacion.objects.create(
            pedido=self.pedido_entregado, repartidor=self.repartidor, estrellas=4,
            comentario='Bien'
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self._url_calificacion(self.pedido_entregado.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['estrellas'], 4)

    def test_obtener_calificacion_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self._url_calificacion(self.pedido_entregado.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pedido_serializer_incluye_calificacion_anidada(self):
        Calificacion.objects.create(
            pedido=self.pedido_entregado, repartidor=self.repartidor, estrellas=5,
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get('/api/auth/pedidos/')
        pedido_data = next(
            p for p in response.data if p['id'] == self.pedido_entregado.id
        )
        self.assertIsNotNone(pedido_data['calificacion'])
        self.assertEqual(pedido_data['calificacion']['estrellas'], 5)


# ─────────────────────────────────────────────────────────────────
# 10. ENDPOINT — Promedio de calificaciones del repartidor (Incidencia 3)
# ─────────────────────────────────────────────────────────────────

class PromedioCalificacionesEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        crear_rol('repartidor')
        self.repartidor = crear_usuario('repartidor_prom@test.com', rol_nombre='repartidor')
        self.cliente = crear_usuario('cliente_prom@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.cliente,
            nombre='Negocio Prom',
            direccion='Av. Prom 1',
        )
        self.url = '/api/auth/repartidor/calificaciones/promedio/'

    def _crear_pedido_calificado(self, estrellas):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            repartidor=self.repartidor,
            estado='entregado',
            total=10.00,
            direccion_entrega='Calle 1',
        )
        Calificacion.objects.create(pedido=pedido, repartidor=self.repartidor, estrellas=estrellas)

    def test_promedio_sin_calificaciones_retorna_null(self):
        self.client.force_authenticate(user=self.repartidor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['promedio'])
        self.assertEqual(response.data['total'], 0)

    def test_promedio_con_calificaciones(self):
        self._crear_pedido_calificado(5)
        self._crear_pedido_calificado(3)
        self.client.force_authenticate(user=self.repartidor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['promedio'], 4.0)
        self.assertEqual(response.data['total'], 2)

    def test_promedio_rechaza_no_repartidor(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ─────────────────────────────────────────────────────────────────
# 11. ENDPOINT — Pago con método 'tarjeta' (Incidencia 5, simulado)
# ─────────────────────────────────────────────────────────────────

class PagoTarjetaEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.cliente = crear_usuario('cliente_pago@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_pago@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner,
            nombre='Negocio Pago',
            direccion='Av. Pago 1',
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado='pendiente',
            total=30.00,
            direccion_entrega='Calle Pago 1',
        )

    def test_pagar_con_tarjeta_sin_datos_sensibles_retorna_201(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            f'/api/auth/pedidos/{self.pedido.id}/pagar/',
            {'metodo': 'tarjeta'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pago = Pago.objects.get(pedido=self.pedido)
        self.assertEqual(pago.metodo, 'tarjeta')


# ─────────────────────────────────────────────────────────────────
# 12. HU14 — Distribución de ingresos al confirmarse un pago
# ─────────────────────────────────────────────────────────────────

class DistribucionPagoTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.cliente = crear_usuario('cliente_dist@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_dist@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner,
            nombre='Negocio Distribucion',
            direccion='Av. Dist 1',
            comision_porcentaje=Decimal('20.00'),
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado='pendiente',
            total=Decimal('100.00'),
            direccion_entrega='Calle Dist 1',
        )

    def test_pagar_calcula_y_persiste_distribucion(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            f'/api/auth/pedidos/{self.pedido.id}/pagar/',
            {'metodo': 'yape'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        pago = Pago.objects.get(pedido=self.pedido)
        # 20% negocio + 10% repartidor (default) sobre 100.00
        self.assertEqual(pago.comision_plataforma, Decimal('20.00'))
        self.assertEqual(pago.monto_repartidor, Decimal('10.00'))
        self.assertEqual(pago.monto_comercio, Decimal('70.00'))
        # la suma de las partes siempre reconstruye el monto total
        self.assertEqual(
            pago.comision_plataforma + pago.monto_comercio + pago.monto_repartidor,
            pago.monto
        )

    def test_distribucion_respeta_comision_propia_de_cada_negocio(self):
        otro_owner = crear_usuario('otro_negocio_dist@test.com', rol_nombre='cliente')
        otro_negocio = Negocio.objects.create(
            propietario=otro_owner,
            nombre='Otro Negocio',
            direccion='Av. Otro 1',
            comision_porcentaje=Decimal('5.00'),
        )
        pedido2 = Pedido.objects.create(
            cliente=self.cliente,
            negocio=otro_negocio,
            estado='pendiente',
            total=Decimal('100.00'),
            direccion_entrega='Calle Otro 1',
        )
        self.client.force_authenticate(user=self.cliente)
        self.client.post(
            f'/api/auth/pedidos/{pedido2.id}/pagar/', {'metodo': 'plin'}, format='json'
        )
        pago2 = Pago.objects.get(pedido=pedido2)
        self.assertEqual(pago2.comision_plataforma, Decimal('5.00'))
        self.assertEqual(pago2.monto_comercio, Decimal('85.00'))


# ─────────────────────────────────────────────────────────────────
# 13. HU15 — Historial de pagos (GET /pagos/)
# ─────────────────────────────────────────────────────────────────

class HistorialPagosEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        crear_rol('admin')
        crear_rol('repartidor')

        self.admin = crear_usuario('admin_pagos@test.com', rol_nombre='admin')
        self.cliente = crear_usuario('cliente_hist@test.com', rol_nombre='cliente')
        self.repartidor = crear_usuario(
            'repartidor_hist@test.com', rol_nombre='repartidor',
            nombre='Carlos', apellido='Lopez',
        )
        self.negocio = Negocio.objects.create(
            propietario=self.cliente,
            nombre='Pollería El Buen Sabor',
            direccion='Av. Hist 1',
            comision_porcentaje=Decimal('15.00'),
        )
        self.url = '/api/auth/pagos/'

    def _crear_pago(self, fecha=None, repartidor=None):
        pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            repartidor=repartidor,
            estado='entregado',
            total=Decimal('50.00'),
            direccion_entrega='Calle Hist 1',
        )
        pago = Pago.objects.create(
            pedido=pedido, monto=Decimal('50.00'), metodo='yape',
            comision_plataforma=Decimal('7.50'),
            monto_comercio=Decimal('37.50'),
            monto_repartidor=Decimal('5.00'),
        )
        if fecha:
            Pago.objects.filter(pk=pago.pk).update(fecha=fecha)
            pago.refresh_from_db()
        return pago

    def test_listar_pagos_requiere_admin(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listar_pagos_como_admin_incluye_distribucion(self):
        self._crear_pago(repartidor=self.repartidor)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(Decimal(str(item['monto_total'])), Decimal('50.00'))
        self.assertEqual(Decimal(str(item['comision_plataforma'])), Decimal('7.50'))
        self.assertEqual(item['negocio_nombre'], 'Pollería El Buen Sabor')
        self.assertEqual(item['repartidor_nombre'], 'Carlos Lopez')

    def test_listar_pagos_sin_repartidor_asignado(self):
        self._crear_pago(repartidor=None)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertIsNone(response.data[0]['repartidor_nombre'])

    def test_filtro_por_rango_de_fechas(self):
        from django.utils import timezone
        from datetime import timedelta

        hoy = timezone.now()
        self._crear_pago(fecha=hoy - timedelta(days=10))
        pago_reciente = self._crear_pago(fecha=hoy)

        self.client.force_authenticate(user=self.admin)
        desde = (hoy - timedelta(days=1)).date().isoformat()
        hasta = hoy.date().isoformat()
        response = self.client.get(self.url, {'desde': desde, 'hasta': hasta})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], pago_reciente.id)

    def test_filtro_con_fecha_invalida_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'desde': 'no-es-una-fecha'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────
# 14. HU16 — Registrar incidencia (POST /pedidos/<id>/incidencias/)
# ─────────────────────────────────────────────────────────────────

class CrearIncidenciaEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.cliente = crear_usuario('cliente_inc@test.com', rol_nombre='cliente')
        self.otro_cliente = crear_usuario('otro_cliente_inc@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_inc@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner,
            nombre='Negocio Incidencia',
            direccion='Av. Inc 1',
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado='entregado',
            total=Decimal('20.00'),
            direccion_entrega='Calle Inc 1',
        )

    def _url(self, pk):
        return f'/api/auth/pedidos/{pk}/incidencias/'

    def test_crear_incidencia_retorna_201(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url(self.pedido.id),
            {'tipo': 'pedido_no_llego', 'descripcion': 'Nunca llegó el pedido'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['estado'], 'abierto')
        self.assertEqual(response.data['respuesta'], None)
        self.assertEqual(response.data['cliente_nombre'], 'Test User')

        incidencia = Incidencia.objects.get(pedido=self.pedido)
        self.assertEqual(incidencia.cliente, self.cliente)
        self.assertEqual(incidencia.tipo, 'pedido_no_llego')

    def test_crear_incidencia_de_pedido_ajeno_retorna_403(self):
        self.client.force_authenticate(user=self.otro_cliente)
        response = self.client.post(
            self._url(self.pedido.id),
            {'tipo': 'otro', 'descripcion': 'algo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_crear_segunda_incidencia_activa_retorna_400(self):
        Incidencia.objects.create(
            pedido=self.pedido, cliente=self.cliente,
            tipo='pedido_incompleto', descripcion='Faltó un producto',
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url(self.pedido.id),
            {'tipo': 'otro', 'descripcion': 'otra cosa'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_crear_incidencia_permitida_si_la_anterior_esta_resuelta(self):
        Incidencia.objects.create(
            pedido=self.pedido, cliente=self.cliente,
            tipo='pedido_incompleto', descripcion='Faltó un producto',
            estado='resuelto',
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url(self.pedido.id),
            {'tipo': 'otro', 'descripcion': 'otra cosa'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_tipo_invalido_retorna_400(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url(self.pedido.id),
            {'tipo': 'no_es_un_tipo_valido', 'descripcion': 'algo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pedido_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.post(
            self._url(999999),
            {'tipo': 'otro', 'descripcion': 'algo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pedido_serializer_incluye_incidencia_anidada(self):
        Incidencia.objects.create(
            pedido=self.pedido, cliente=self.cliente,
            tipo='cobro_incorrecto', descripcion='Me cobraron de más',
        )
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get('/api/auth/pedidos/')
        pedido_data = next(p for p in response.data if p['id'] == self.pedido.id)
        self.assertIsNotNone(pedido_data['incidencia'])
        self.assertEqual(pedido_data['incidencia']['tipo'], 'cobro_incorrecto')


# ─────────────────────────────────────────────────────────────────
# 15. HU17 — Gestión de reclamos (GET /incidencias/, PUT /incidencias/<id>/responder/)
# ─────────────────────────────────────────────────────────────────

class GestionIncidenciasEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        crear_rol('admin')
        crear_rol('repartidor')

        self.admin = crear_usuario('admin_inc@test.com', rol_nombre='admin')
        self.cliente = crear_usuario('cliente_gestion@test.com', rol_nombre='cliente')
        self.repartidor = crear_usuario('repartidor_gestion@test.com', rol_nombre='repartidor')
        self.negocio_owner = crear_usuario('negocio_gestion@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner,
            nombre='Negocio Gestion',
            direccion='Av. Gestion 1',
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente,
            negocio=self.negocio,
            estado='entregado',
            total=Decimal('15.00'),
            direccion_entrega='Calle Gestion 1',
        )
        self.incidencia = Incidencia.objects.create(
            pedido=self.pedido, cliente=self.cliente,
            tipo='producto_danado', descripcion='Llegó roto',
        )

    def test_listar_incidencias_requiere_admin(self):
        for user in (self.cliente, self.repartidor):
            self.client.force_authenticate(user=user)
            response = self.client.get('/api/auth/incidencias/')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listar_incidencias_como_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/auth/incidencias/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.incidencia.id)

    def test_filtrar_incidencias_por_estado(self):
        Incidencia.objects.create(
            pedido=self.pedido, cliente=self.cliente,
            tipo='otro', descripcion='otra', estado='resuelto',
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get('/api/auth/incidencias/', {'estado': 'abierto'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['estado'], 'abierto')

        response = self.client.get('/api/auth/incidencias/', {'estado': 'resuelto'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['estado'], 'resuelto')

    def test_filtrar_por_estado_invalido_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/auth/incidencias/', {'estado': 'no_existe'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_responder_incidencia_actualiza_estado_y_respuesta(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(
            f'/api/auth/incidencias/{self.incidencia.id}/responder/',
            {'estado': 'resuelto', 'respuesta': 'Se coordinó reembolso.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['estado'], 'resuelto')
        self.assertEqual(response.data['respuesta'], 'Se coordinó reembolso.')

        self.incidencia.refresh_from_db()
        self.assertEqual(self.incidencia.estado, 'resuelto')
        self.assertEqual(self.incidencia.respuesta, 'Se coordinó reembolso.')

    def test_responder_incidencia_requiere_admin(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.put(
            f'/api/auth/incidencias/{self.incidencia.id}/responder/',
            {'estado': 'resuelto', 'respuesta': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_responder_con_estado_invalido_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(
            f'/api/auth/incidencias/{self.incidencia.id}/responder/',
            {'estado': 'no_es_valido', 'respuesta': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_responder_incidencia_inexistente_retorna_404(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(
            '/api/auth/incidencias/999999/responder/',
            {'estado': 'resuelto', 'respuesta': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────
# 16. HU18 — Reporte diario (GET /reportes/diario/)
# ─────────────────────────────────────────────────────────────────

class ReporteDiarioEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('admin')
        crear_rol('cliente')
        self.admin = crear_usuario('admin_rep@test.com', rol_nombre='admin')
        self.cliente = crear_usuario('cliente_rep@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_rep@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner, nombre='Negocio Reporte', direccion='Av. Rep 1',
        )
        self.url = '/api/auth/reportes/diario/'

    def _crear_pedido(self, estado='pendiente', total=Decimal('10.00')):
        return Pedido.objects.create(
            cliente=self.cliente, negocio=self.negocio, estado=estado,
            total=total, direccion_entrega='Calle Rep 1',
        )

    def test_requiere_admin(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reporte_usa_hoy_por_defecto(self):
        self._crear_pedido()
        self._crear_pedido(estado='cancelado')
        pedido_pagado = self._crear_pedido(total=Decimal('50.00'))
        Pago.objects.create(pedido=pedido_pagado, monto=Decimal('50.00'), metodo='yape')

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fecha'], timezone.localdate().isoformat())
        self.assertEqual(response.data['total_pedidos'], 3)
        self.assertEqual(response.data['cancelaciones'], 1)
        self.assertEqual(response.data['ingresos'], 50.00)

    def test_reporte_con_fecha_especifica_sin_datos(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'fecha': '2020-01-01'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_pedidos'], 0)
        self.assertEqual(response.data['ingresos'], 0.0)
        self.assertEqual(response.data['cancelaciones'], 0)

    def test_fecha_invalida_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'fecha': 'no-es-fecha'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────
# 17. HU19 — Reporte por comercio (GET /negocio/reporte/)
# ─────────────────────────────────────────────────────────────────

class ReporteNegocioEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.owner = crear_usuario('owner_reporte@test.com', rol_nombre='cliente')
        self.otro_owner = crear_usuario('otro_owner_reporte@test.com', rol_nombre='cliente')
        self.cliente = crear_usuario('comprador_reporte@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.owner, nombre='Negocio Ventas', direccion='Av. Ventas 1',
        )
        self.producto1 = Producto.objects.create(
            negocio=self.negocio, nombre='Combo familiar', precio=Decimal('20.00'),
        )
        self.producto2 = Producto.objects.create(
            negocio=self.negocio, nombre='Gaseosa 1L', precio=Decimal('5.00'),
        )
        self.url = '/api/auth/negocio/reporte/'

    def _crear_pedido_pagado(self, fecha, detalles):
        total = sum(cantidad * producto.precio for producto, cantidad in detalles)
        pedido = Pedido.objects.create(
            cliente=self.cliente, negocio=self.negocio, estado='completado',
            total=total, direccion_entrega='Calle Ventas 1',
        )
        for producto, cantidad in detalles:
            DetallePedido.objects.create(
                pedido=pedido, producto=producto, cantidad=cantidad,
                precio_unitario=producto.precio,
            )
        pago = Pago.objects.create(pedido=pedido, monto=total, metodo='yape')
        Pago.objects.filter(pk=pago.pk).update(fecha=fecha)
        return pedido

    def test_requiere_ser_dueno_de_negocio(self):
        self.client.force_authenticate(user=self.otro_owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reporte_agrega_ventas_productos_y_dias(self):
        hoy = timezone.now()
        self._crear_pedido_pagado(hoy, [(self.producto1, 2), (self.producto2, 3)])
        self._crear_pedido_pagado(hoy - timedelta(days=1), [(self.producto1, 1)])

        self.client.force_authenticate(user=self.owner)
        desde = (hoy - timedelta(days=1)).date().isoformat()
        hasta = hoy.date().isoformat()
        response = self.client.get(self.url, {'desde': desde, 'hasta': hasta})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ventas_totales'], 75.00)  # (40+15) + 20

        productos = {p['producto_id']: p for p in response.data['productos_mas_vendidos']}
        self.assertEqual(productos[self.producto1.id]['cantidad_vendida'], 3)
        self.assertEqual(productos[self.producto1.id]['ingresos'], 60.00)
        self.assertEqual(productos[self.producto2.id]['cantidad_vendida'], 3)

        self.assertEqual(len(response.data['ventas_por_dia']), 2)
        self.assertEqual(response.data['ventas_por_dia'][0]['fecha'], desde)
        self.assertEqual(response.data['ventas_por_dia'][1]['fecha'], hasta)
        self.assertEqual(response.data['ventas_por_dia'][0]['total'], 20.00)
        self.assertEqual(response.data['ventas_por_dia'][1]['total'], 55.00)

    def test_dias_sin_ventas_aparecen_con_total_cero(self):
        self.client.force_authenticate(user=self.owner)
        hoy = timezone.localdate()
        desde = (hoy - timedelta(days=2)).isoformat()
        response = self.client.get(self.url, {'desde': desde, 'hasta': hoy.isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['ventas_por_dia']), 3)
        for dia in response.data['ventas_por_dia']:
            self.assertEqual(dia['total'], 0.0)
        self.assertEqual(response.data['ventas_totales'], 0.0)
        self.assertEqual(response.data['productos_mas_vendidos'], [])

    def test_rango_por_defecto_es_7_dias(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['ventas_por_dia']), 7)

    def test_desde_posterior_a_hasta_retorna_400(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url, {'desde': '2026-07-10', 'hasta': '2026-07-01'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fecha_invalida_retorna_400(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url, {'desde': 'no-es-fecha'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────
# 18. HU20 — Predicción de demanda (GET /predicciones/demanda/)
# ─────────────────────────────────────────────────────────────────

class PrediccionDemandaEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('admin')
        crear_rol('cliente')
        self.admin = crear_usuario('admin_pred@test.com', rol_nombre='admin')
        self.cliente = crear_usuario('cliente_pred@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_pred@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner, nombre='Negocio Prediccion', direccion='Av. Pred 1',
        )
        self.url = '/api/auth/predicciones/demanda/'

    def _crear_pedidos(self, fecha, cantidad):
        for _ in range(cantidad):
            pedido = Pedido.objects.create(
                cliente=self.cliente, negocio=self.negocio, estado='pendiente',
                total=Decimal('10.00'), direccion_entrega='Calle Pred 1',
            )
            Pedido.objects.filter(pk=pedido.pk).update(created_at=fecha)

    def test_requiere_admin(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_historico_incluye_dias_sin_pedidos_y_respeta_dias_historico(self):
        hoy = timezone.now()
        self._crear_pedidos(hoy, 5)
        self._crear_pedidos(hoy - timedelta(days=2), 3)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'dias_historico': 4, 'dias_prediccion': 3})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        historico = response.data['historico']
        self.assertEqual(len(historico), 4)
        self.assertEqual(historico[-1]['fecha'], timezone.localdate().isoformat())
        self.assertEqual(historico[-1]['pedidos'], 5)
        self.assertEqual(historico[-3]['pedidos'], 3)
        # días sin pedidos deben aparecer con 0, no faltar
        self.assertEqual(historico[-2]['pedidos'], 0)

    def test_prediccion_tiene_la_longitud_pedida_y_empieza_manana(self):
        hoy = timezone.now()
        self._crear_pedidos(hoy, 10)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'dias_historico': 7, 'dias_prediccion': 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prediccion = response.data['prediccion']
        self.assertEqual(len(prediccion), 5)
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(prediccion[0]['fecha'], manana)
        self.assertEqual(response.data['prediccion_manana'], prediccion[0]['pedidos'])

    def test_sin_historico_prediccion_es_cero(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'dias_historico': 5, 'dias_prediccion': 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for h in response.data['historico']:
            self.assertEqual(h['pedidos'], 0)
        for p in response.data['prediccion']:
            self.assertEqual(p['pedidos'], 0)
        self.assertEqual(response.data['prediccion_manana'], 0)

    def test_parametros_por_defecto(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['historico']), 14)
        self.assertEqual(len(response.data['prediccion']), 7)

    def test_parametro_no_numerico_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'dias_historico': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parametro_fuera_de_rango_retorna_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url, {'dias_historico': 500})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────
# 19. AUDITORÍA — Disponibilidad de repartidor (PUT /repartidor/perfil/)
# ─────────────────────────────────────────────────────────────────

class DisponibilidadRepartidorEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('repartidor')
        self.repartidor = crear_usuario('repartidor_disp@test.com', rol_nombre='repartidor')
        self.perfil = PerfilRepartidor.objects.create(
            usuario=self.repartidor, dni='12345678', vehiculo='moto', disponible=True,
        )
        self.url = '/api/auth/repartidor/perfil/'

    def test_put_disponible_false_persiste(self):
        self.client.force_authenticate(user=self.repartidor)
        response = self.client.put(self.url, {'disponible': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['disponible'], False)

        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.disponible)

    def test_put_disponible_true_luego_false_alterna_correctamente(self):
        self.client.force_authenticate(user=self.repartidor)
        self.client.put(self.url, {'disponible': False}, format='json')
        response = self.client.put(self.url, {'disponible': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.disponible)


# ─────────────────────────────────────────────────────────────────
# 20. AUDITORÍA — Registros legacy con telefono/dni vacíos no rompen el login
# ─────────────────────────────────────────────────────────────────

class LoginConDatosLegacyTest(APITestCase):

    def test_login_funciona_con_telefono_vacio_legacy(self):
        crear_rol('cliente')
        # Simula un registro legacy previo a la validación (bypass del serializer).
        usuario = Usuario.objects.create_user(
            email='legacy@test.com', password='Legacy123!',
            nombre='Legacy', apellido='User', telefono='',
        )
        response = self.client.post(
            '/api/auth/login/',
            {'email': 'legacy@test.com', 'password': 'Legacy123!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)


# ─────────────────────────────────────────────────────────────────
# 21. AUDITORÍA — GET /pedidos/<id>/detalle/ incluye el pago
# ─────────────────────────────────────────────────────────────────

class DetallePedidoConPagoEndpointTest(APITestCase):

    def setUp(self):
        crear_rol('cliente')
        self.cliente = crear_usuario('cliente_detalle@test.com', rol_nombre='cliente')
        self.negocio_owner = crear_usuario('negocio_detalle@test.com', rol_nombre='cliente')
        self.negocio = Negocio.objects.create(
            propietario=self.negocio_owner, nombre='Negocio Detalle', direccion='Av. Detalle 1',
        )
        self.pedido = Pedido.objects.create(
            cliente=self.cliente, negocio=self.negocio, estado='pendiente',
            total=Decimal('25.00'), direccion_entrega='Calle Detalle 1',
        )
        self.url = f'/api/auth/pedidos/{self.pedido.id}/detalle/'

    def test_detalle_sin_pago_muestra_pago_null(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['pago'])

    def test_detalle_con_pago_lo_incluye_poblado(self):
        Pago.objects.create(pedido=self.pedido, monto=self.pedido.total, metodo='yape')
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['pago'])
        self.assertEqual(response.data['pago']['metodo'], 'yape')

    def test_detalle_pedido_ajeno_retorna_404(self):
        otro_cliente = crear_usuario('otro_detalle@test.com', rol_nombre='cliente')
        self.client.force_authenticate(user=otro_cliente)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)