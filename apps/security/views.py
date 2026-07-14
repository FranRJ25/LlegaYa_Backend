from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Sum, F, Count
from django.db.models.functions import TruncDate
from collections import defaultdict
import os

from .cookies import REFRESH_COOKIE_NAME, set_refresh_cookie, delete_refresh_cookie

from .models import Usuario, Rol, Negocio, Producto, Pedido,DetallePedido, PasswordResetToken, HistorialCambioProducto, PerfilRepartidor, Pago, Calificacion, Incidencia
from .serializers import (
    RegisterSerializer, UsuarioSerializer,
    CustomTokenObtainPairSerializer,
    NegocioSerializer, NegocioCreateSerializer,
    ProductoSerializer, PedidoSerializer,
    HistorialCambioSerializer, PerfilRepartidorSerializer,
    RegisterRepartidorSerializer, RepartidorSerializer, PagoSerializer, PedidoConPagoSerializer,
    CalificacionSerializer, HistorialPagoSerializer, IncidenciaSerializer,
)
from .permissions import EsAdmin, EsCliente, EsRepartidor, EsPropietarioDeNegocio, EsAdminORepartidor


# ──────────────────────────────────────────
# AUTENTICACIÓN
# ──────────────────────────────────────────

class RegisterRepartidorView(APIView):
    """
    POST /api/auth/repartidor/register/
    Registra un nuevo repartidor en su propia tabla (sin vincularse a Usuario).
    No requiere token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterRepartidorSerializer(data=request.data)
        if serializer.is_valid():
            repartidor = serializer.save()
            return Response(
                {
                    'mensaje': 'Repartidor registrado correctamente',
                    'repartidor': RepartidorSerializer(repartidor).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CookieTokenRefreshView(APIView):
    """
    POST /api/auth/token/refresh/
    Lee el refresh_token desde la cookie HttpOnly, devuelve {access}.
    No requiere cabecera Authorization.
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not raw:
            return Response({'detail': 'No hay refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': raw})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            resp = Response({'detail': 'Refresh inválido o expirado'}, status=status.HTTP_401_UNAUTHORIZED)
            delete_refresh_cookie(resp)
            return resp

        data = serializer.validated_data        # {'access': ...} y 'refresh' si hay rotación
        resp = Response({'access': data['access']}, status=status.HTTP_200_OK)
        if 'refresh' in data:                   # rotación activa: renueva la cookie
            set_refresh_cookie(resp, data['refresh'])
        return resp


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Devuelve {access, usuario}. El refresh_token va SOLO en cookie HttpOnly.
    """
    serializer_class       = CustomTokenObtainPairSerializer
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        data    = serializer.validated_data          # {access, refresh, usuario}
        refresh = data.pop('refresh')                # saca refresh del body

        resp = Response(data, status=status.HTTP_200_OK)   # devuelve {access, usuario}
        set_refresh_cookie(resp, refresh)
        return resp


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Crea un usuario nuevo como 'cliente' o 'repartidor'.
    No requiere token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            return Response(
                {
                    'mensaje': 'Usuario registrado correctamente',
                    'usuario': UsuarioSerializer(usuario).data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Lee el refresh_token desde la cookie, lo invalida (blacklist) y borra la cookie.
    No requiere cabecera Authorization.
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw  = request.COOKIES.get(REFRESH_COOKIE_NAME)
        resp = Response({'detail': 'Sesión cerrada correctamente'}, status=status.HTTP_200_OK)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except Exception:
                pass
        delete_refresh_cookie(resp)
        return resp


class PerfilView(APIView):
    """
    GET  /api/auth/perfil/    → ver mi perfil
    PUT  /api/auth/perfil/    → editar mis datos
    Requiere: Bearer token válido.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def put(self, request):
        serializer = UsuarioSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PerfilRepartidorView(APIView):
    """
    GET  /api/auth/repartidor/perfil/  → ver mi perfil de repartidor
    PUT  /api/auth/repartidor/perfil/  → editar mi perfil de repartidor
    Requiere: Bearer token + rol repartidor.
    """
    permission_classes = [IsAuthenticated, EsRepartidor]

    def get(self, request):
        try:
            perfil = request.user.perfil_repartidor
        except Exception:
            return Response(
                {'error': 'Perfil de repartidor no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(PerfilRepartidorSerializer(perfil).data)

    def put(self, request):
        try:
            perfil = request.user.perfil_repartidor
        except Exception:
            return Response(
                {'error': 'Perfil de repartidor no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = PerfilRepartidorSerializer(perfil, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────
# ADMINISTRACIÓN (solo admin)
# ──────────────────────────────────────────

class ListaUsuariosView(APIView):
    """
    GET /api/auth/admin/usuarios/
    Lista todos los usuarios del sistema.
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def get(self, request):
        usuarios = Usuario.objects.select_related('rol').all()
        return Response(UsuarioSerializer(usuarios, many=True).data)


class CambiarRolView(APIView):
    """
    PUT /api/auth/admin/usuarios/<id>/rol/
    Cambia el rol de un usuario.
    Requiere: rol admin.
    Body: { "rol": "repartidor" }
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def put(self, request, pk):
        try:
            usuario = Usuario.objects.get(pk=pk)
            rol     = Rol.objects.get(nombre=request.data.get('rol'))
            usuario.rol = rol
            usuario.save()
            return Response({'mensaje': f'Rol actualizado a {rol.nombre}'})
        except Usuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Rol.DoesNotExist:
            return Response({'error': 'Rol inválido'}, status=status.HTTP_400_BAD_REQUEST)


class ToggleEstadoUsuarioView(APIView):
    """
    PUT /api/auth/admin/usuarios/<id>/estado/
    Activa o desactiva a un usuario (Soft Delete).
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def put(self, request, pk):
        try:
            usuario = Usuario.objects.get(pk=pk)
            usuario.activo = not usuario.activo
            usuario.save()
            
            estado_str = "activado" if usuario.activo else "desactivado"
            return Response({'mensaje': f'Usuario {usuario.nombre} ha sido {estado_str}'})
        except Usuario.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

# ──────────────────────────────────────────
# NEGOCIOS
# ──────────────────────────────────────────

class MiNegocioView(APIView):
    """
    GET  /api/auth/negocio/    → ver mi negocio
    POST /api/auth/negocio/    → registrar mi negocio
    Requiere: estar autenticado.
    Cualquier usuario puede registrar un negocio (clientes también).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return Response(NegocioSerializer(request.user.negocio).data)
        except Negocio.DoesNotExist:
            return Response({'error': 'No tienes un negocio registrado'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        if hasattr(request.user, 'negocio'):
            return Response({'error': 'Ya tienes un negocio registrado'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = NegocioCreateSerializer(data=request.data)
        if serializer.is_valid():
            negocio = serializer.save(propietario=request.user)
            return Response(NegocioSerializer(negocio).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        try:
            negocio = request.user.negocio
        except Negocio.DoesNotExist:
            return Response({'error': 'No tienes un negocio registrado'}, status=404)
        serializer = NegocioCreateSerializer(negocio, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(NegocioSerializer(negocio).data)
        return Response(serializer.errors, status=400)

class ListaNegociosView(APIView):
    """
    GET /api/auth/negocios/
    Lista todos los negocios activos.
    Requiere: estar autenticado (cualquier rol puede ver negocios).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        negocios = Negocio.objects.filter(activo=True).select_related('propietario')
        return Response(NegocioSerializer(negocios, many=True).data)


# ──────────────────────────────────────────
# PRODUCTOS
# ──────────────────────────────────────────

def _registrar_cambio(producto, usuario, tipo, valor_anterior='', valor_nuevo='', comentario=''):
    """Helper para crear entradas del historial."""
    return HistorialCambioProducto.objects.create(
        producto=producto,
        usuario=usuario,
        tipo_cambio=tipo,
        valor_anterior=str(valor_anterior) if valor_anterior is not None else '',
        valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else '',
        comentario=comentario,
    )

class ProductosNegocioView(APIView):
    """
    GET  /api/auth/negocio/productos/   → ver mis productos (HU05)
    POST /api/auth/negocio/productos/   → crear producto (HU05)
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def get(self, request):
        productos = Producto.objects.filter(negocio=request.user.negocio).order_by('-created_at', '-id')
        return Response(ProductoSerializer(productos, many=True).data)

    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            producto = serializer.save(negocio=request.user.negocio)
            _registrar_cambio(
                producto=producto,
                usuario=request.user,
                tipo='creacion',
                valor_nuevo=producto.nombre,
                comentario=f'Precio inicial: S/ {producto.precio}',
            )
            return Response(ProductoSerializer(producto).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProductoDetalleView(APIView):
    """
    GET    /api/auth/negocio/productos/<id>/   → ver producto
    PUT    /api/auth/negocio/productos/<id>/   → editar completo
    PATCH  /api/auth/negocio/productos/<id>/   → editar parcial
    DELETE /api/auth/negocio/productos/<id>/   → eliminar producto
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def _get_producto(self, request, pk):
        try:
            return Producto.objects.get(pk=pk, negocio=request.user.negocio)
        except Producto.DoesNotExist:
            return None

    def get(self, request, pk):
        producto = self._get_producto(request, pk)
        if not producto:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductoSerializer(producto).data)

    def _aplicar_cambios(self, producto, request, partial=False):
        anteriores = {
            'nombre':      producto.nombre,
            'descripcion': producto.descripcion,
            'precio':      producto.precio,
            'categoria':   producto.categoria,
            'disponible':  producto.disponible,
        }
        serializer = ProductoSerializer(producto, data=request.data, partial=partial)
        if not serializer.is_valid():
            return None, Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        producto = serializer.save()

        cambios = []
        if str(anteriores['precio']) != str(producto.precio):
            _registrar_cambio(producto, request.user, 'precio',
                              f'S/ {anteriores["precio"]}', f'S/ {producto.precio}')
            cambios.append('precio')
        if anteriores['disponible'] != producto.disponible:
            _registrar_cambio(producto, request.user, 'disponible',
                              'Disponible' if anteriores['disponible'] else 'No disponible',
                              'Disponible' if producto.disponible else 'No disponible')
            cambios.append('disponible')
        if anteriores['nombre'] != producto.nombre:
            _registrar_cambio(producto, request.user, 'nombre',
                              anteriores['nombre'], producto.nombre)
            cambios.append('nombre')
        if anteriores['descripcion'] != producto.descripcion:
            _registrar_cambio(producto, request.user, 'descripcion',
                              anteriores['descripcion'][:80] or '(vacío)',
                              producto.descripcion[:80] or '(vacío)')
            cambios.append('descripcion')
        if anteriores['categoria'] != producto.categoria:
            _registrar_cambio(producto, request.user, 'categoria',
                              anteriores['categoria'], producto.categoria)
            cambios.append('categoria')

        return producto, Response(
            {**ProductoSerializer(producto).data, 'cambios_registrados': cambios},
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk):
        producto = self._get_producto(request, pk)
        if not producto:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        _, resp = self._aplicar_cambios(producto, request, partial=False)
        return resp

    def patch(self, request, pk):
        producto = self._get_producto(request, pk)
        if not producto:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        _, resp = self._aplicar_cambios(producto, request, partial=True)
        return resp

    def delete(self, request, pk):
        producto = self._get_producto(request, pk)
        if not producto:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        nombre_borrado = producto.nombre
        producto.delete()
        return Response(
            {'mensaje': f'Producto "{nombre_borrado}" eliminado correctamente'},
            status=status.HTTP_200_OK,
        )
    
class ToggleDisponibilidadProductoView(APIView):
    """
    PATCH /api/auth/negocio/productos/<id>/disponibilidad/
    HU06 - atajo dedicado para activar/desactivar un producto.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def patch(self, request, pk):
        try:
            producto = Producto.objects.get(pk=pk, negocio=request.user.negocio)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        anterior = producto.disponible
        producto.disponible = not producto.disponible
        producto.save(update_fields=['disponible', 'updated_at'])

        _registrar_cambio(
            producto, request.user, 'disponible',
            'Disponible' if anterior else 'No disponible',
            'Disponible' if producto.disponible else 'No disponible',
        )

        return Response({
            'mensaje': (
                f'Producto "{producto.nombre}" ahora está '
                f'{"disponible" if producto.disponible else "no disponible"}.'
            ),
            'producto': ProductoSerializer(producto).data,
        })

class ActualizarPrecioProductoView(APIView):
    """
    PATCH /api/auth/negocio/productos/<id>/precio/   { "precio": 12.50 }
    HU06 - atajo dedicado para modificar solo el precio.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def patch(self, request, pk):
        try:
            producto = Producto.objects.get(pk=pk, negocio=request.user.negocio)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        nuevo = request.data.get('precio')
        if nuevo in (None, ''):
            return Response({'error': 'El campo "precio" es obligatorio.'}, status=400)
        try:
            nuevo_decimal = Decimal(str(nuevo))
        except (InvalidOperation, TypeError):
            return Response({'error': 'Precio inválido.'}, status=400)
        if nuevo_decimal <= 0:
            return Response({'error': 'El precio debe ser mayor a 0.'}, status=400)

        anterior = producto.precio
        if anterior == nuevo_decimal:
            return Response({
                'mensaje': 'El precio no cambió.',
                'producto': ProductoSerializer(producto).data,
            })

        producto.precio = nuevo_decimal
        producto.save(update_fields=['precio', 'updated_at'])

        _registrar_cambio(
            producto, request.user, 'precio',
            f'S/ {anterior}', f'S/ {nuevo_decimal}',
            comentario=request.data.get('comentario', ''),
        )

        return Response({
            'mensaje': f'Precio actualizado: S/ {anterior} → S/ {nuevo_decimal}',
            'producto': ProductoSerializer(producto).data,
        })

class HistorialProductoView(APIView):
    """
    GET /api/auth/negocio/productos/<id>/historial/
    HU06 - Devuelve el historial de cambios de un producto.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def get(self, request, pk):
        try:
            producto = Producto.objects.get(pk=pk, negocio=request.user.negocio)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        historial = producto.historial.select_related('usuario').all()
        return Response(HistorialCambioSerializer(historial, many=True).data)

class HistorialCatalogoView(APIView):
    """
    GET /api/auth/negocio/catalogo/historial/?tipo=precio&dias=30
    HU06 - Historial agregado de TODOS los productos del negocio.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def get(self, request):
        qs = HistorialCambioProducto.objects.select_related(
            'producto', 'usuario'
        ).filter(producto__negocio=request.user.negocio)

        tipo = request.query_params.get('tipo')
        if tipo:
            qs = qs.filter(tipo_cambio=tipo)

        dias = request.query_params.get('dias')
        if dias:
            try:
                from django.utils import timezone
                from datetime import timedelta
                desde = timezone.now() - timedelta(days=int(dias))
                qs = qs.filter(fecha__gte=desde)
            except (ValueError, TypeError):
                pass

        return Response(HistorialCambioSerializer(qs[:500], many=True).data)    

# ──────────────────────────────────────────
# PEDIDOS
# ──────────────────────────────────────────

class MisPedidosView(APIView):
    """
    GET /api/auth/pedidos/
    - Si es cliente:     ve sus propios pedidos.
    - Si es repartidor:  ve los pedidos asignados a él.
    - Si es admin:       ve todos los pedidos.
    Requiere: estar autenticado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rol = request.user.rol.nombre if request.user.rol else None

        base_qs = Pedido.objects.select_related(
            'cliente', 'negocio', 'repartidor'
        ).prefetch_related(
            'detalles', 'detalles__producto'
        )

        if rol == 'admin':
            pedidos = base_qs.all()
        elif rol == 'repartidor':
            pedidos = base_qs.filter(repartidor=request.user)
        else:
            pedidos = base_qs.filter(cliente=request.user)

        return Response(PedidoConPagoSerializer(pedidos, many=True).data)


class AsignarRepartidorView(APIView):
    """
    PUT /api/auth/pedidos/<id>/asignar/
    Asigna un repartidor a un pedido.
    Requiere: rol admin.
    Body: { "repartidor_id": 5 }
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def put(self, request, pk):
        try:
            pedido      = Pedido.objects.get(pk=pk)
            repartidor  = Usuario.objects.get(pk=request.data.get('repartidor_id'), rol__nombre='repartidor')
            pedido.repartidor = repartidor
            pedido.estado     = 'confirmado'
            pedido.save()
            return Response({'mensaje': f'Repartidor {repartidor.nombre} asignado al pedido #{pedido.id}'})
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Usuario.DoesNotExist:
            return Response({'error': 'Repartidor no encontrado'}, status=status.HTTP_404_NOT_FOUND)


class ActualizarEstadoPedidoView(APIView):
    """
    PUT /api/auth/pedidos/<id>/estado/
    El repartidor actualiza el estado de su pedido asignado.
    Requiere: rol repartidor, y que el pedido le pertenezca.
    Body: { "estado": "en_camino" }
    """
    permission_classes = [IsAuthenticated, EsRepartidor]

    def put(self, request, pk):
        try:
            pedido = Pedido.objects.get(pk=pk, repartidor=request.user)
            nuevo_estado = request.data.get('estado')
            estados_validos = ['en_camino', 'entregado']
            if nuevo_estado not in estados_validos:
                return Response({'error': f'Estado inválido. Opciones: {estados_validos}'}, status=status.HTTP_400_BAD_REQUEST)
            pedido.estado = nuevo_estado
            pedido.save()
            return Response({'mensaje': f'Pedido #{pedido.id} actualizado a {nuevo_estado}'})
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado o no te pertenece'}, status=status.HTTP_404_NOT_FOUND)


class ProductosPublicosView(APIView):
    """
    GET /api/auth/negocios/<pk>/productos/
    Cualquier cliente autenticado puede ver los productos de un negocio.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            negocio = Negocio.objects.get(pk=pk, activo=True)
        except Negocio.DoesNotExist:
            return Response({'error': 'Negocio no encontrado'}, status=404)

        productos = Producto.objects.filter(negocio=negocio, disponible=True)
        return Response(ProductoSerializer(productos, many=True).data)
    

class ProductosPublicosView(APIView):
    """
    GET /api/auth/negocios/<pk>/productos/
    Cualquier cliente autenticado puede ver los productos de un negocio.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            negocio = Negocio.objects.get(pk=pk, activo=True)
        except Negocio.DoesNotExist:
            return Response({'error': 'Negocio no encontrado'}, status=404)

        productos = Producto.objects.filter(negocio=negocio, disponible=True)
        return Response(ProductoSerializer(productos, many=True).data)


# Vista para crear pedidos
class CrearPedidoView(APIView):
    """
    POST /api/auth/pedidos/crear/
    El cliente envía su carrito y se crean N pedidos (uno por negocio).
    Body: {
      "direccion_entrega": "Av. Arequipa 123",
      "items": [
        { "producto_id": 1, "cantidad": 2 },
        { "producto_id": 5, "cantidad": 1 }
      ]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        direccion = request.data.get('direccion_entrega', '').strip()
        items     = request.data.get('items', [])

        if not direccion:
            return Response({'error': 'La dirección es obligatoria.'}, status=400)
        if not items:
            return Response({'error': 'El carrito está vacío.'}, status=400)

        # Agrupar items por negocio
        grupos: dict = {}
        for item in items:
            try:
                producto = Producto.objects.get(pk=item['producto_id'], disponible=True)
            except Producto.DoesNotExist:
                return Response({'error': f'Producto {item["producto_id"]} no disponible.'}, status=400)

            nid = producto.negocio_id
            if nid not in grupos:
                grupos[nid] = []
            grupos[nid].append({
                'producto': producto,
                'cantidad': int(item['cantidad'])
            })

        # Crear un pedido por cada negocio
        pedidos_creados = []
        for negocio_id, lineas in grupos.items():
            total = sum(l['producto'].precio * l['cantidad'] for l in lineas)

            pedido = Pedido.objects.create(
                cliente=request.user,
                negocio_id=negocio_id,
                direccion_entrega=direccion,
                total=total,
                estado='pendiente'
            )

            for l in lineas:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=l['producto'],
                    cantidad=l['cantidad'],
                    precio_unitario=l['producto'].precio
                )

            pedidos_creados.append(PedidoSerializer(pedido).data)

        return Response({
            'mensaje': f'{len(pedidos_creados)} pedido(s) creado(s) correctamente.',
            'pedidos': pedidos_creados
        }, status=201)

class CancelarPedidoView(APIView):
    """
    PUT /api/auth/pedidos/<id>/cancelar/
    El cliente cancela su pedido (solo si está en 'pendiente').
    Body: { "motivo": "..." }  ← opcional
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            pedido = Pedido.objects.get(pk=pk, cliente=request.user)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if pedido.estado != 'pendiente':
            return Response(
                {'error': 'Solo puedes cancelar pedidos en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        motivo = request.data.get('motivo', '').strip()
        pedido.estado = 'cancelado'
        pedido.motivo_cancelacion = motivo if motivo else None
        pedido.save()

        return Response({
            'mensaje': f'Pedido #{pedido.id} cancelado correctamente.',
            'pedido': PedidoSerializer(pedido).data
        })


class CompletarPedidoView(APIView):
    """
    PUT /api/auth/pedidos/<id>/completar/
    El comercio marca su pedido como completado (solo si está en 'pendiente').
    Requiere: ser propietario del negocio al que pertenece el pedido.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            negocio = request.user.negocio
        except Negocio.DoesNotExist:
            return Response({'error': 'No tienes un negocio registrado.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            pedido = Pedido.objects.get(pk=pk, negocio=negocio)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if pedido.estado != 'pendiente':
            return Response(
                {'error': 'Solo puedes completar pedidos en estado pendiente.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pedido.estado = 'completado'
        pedido.save()

        return Response({
            'mensaje': f'Pedido #{pedido.id} marcado como completado.',
            'pedido': PedidoSerializer(pedido).data
        })
    
def _centavos(valor):
    return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _calcular_distribucion_pago(pedido, monto_total):
    """
    HU14 — Distribución de ingresos. La comisión de la plataforma depende del
    negocio (Negocio.comision_porcentaje); la del repartidor es un % fijo de
    plataforma (settings.REPARTIDOR_COMISION_PORCENTAJE), ya que hoy no existe
    una tarifa de envío propia por pedido.
    """
    comision_negocio_pct    = pedido.negocio.comision_porcentaje
    comision_repartidor_pct = settings.REPARTIDOR_COMISION_PORCENTAJE

    comision_plataforma = _centavos(monto_total * comision_negocio_pct / Decimal('100'))
    monto_repartidor    = _centavos(monto_total * comision_repartidor_pct / Decimal('100'))
    monto_comercio      = monto_total - comision_plataforma - monto_repartidor

    return comision_plataforma, monto_comercio, monto_repartidor


class PagarPedidoView(APIView):
    """
    POST /api/auth/pedidos/<pk>/pagar/
    El cliente paga su pedido. Crea el registro en Pago (1 a 1 con Pedido) y
    calcula y persiste la distribución de ingresos (HU14).
    Body: { "metodo": "yape" }   # tarjeta | yape | plin
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pedido = Pedido.objects.select_related('negocio').get(pk=pk, cliente=request.user)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(pedido, 'pago'):
            return Response({'error': 'Este pedido ya fue pagado.'}, status=status.HTTP_400_BAD_REQUEST)

        metodo = request.data.get('metodo', 'tarjeta')
        if metodo not in dict(Pago.METODOS):
            return Response({'error': 'Método de pago inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        comision_plataforma, monto_comercio, monto_repartidor = _calcular_distribucion_pago(
            pedido, pedido.total
        )

        pago = Pago.objects.create(
            pedido=pedido,
            monto=pedido.total,
            metodo=metodo,
            comision_plataforma=comision_plataforma,
            monto_comercio=monto_comercio,
            monto_repartidor=monto_repartidor,
        )

        return Response({
            'mensaje': 'Pago registrado correctamente.',
            'pedido': PedidoConPagoSerializer(pedido).data
        }, status=status.HTTP_201_CREATED)

class DetallePedidoConPagoView(APIView):
    """
    GET /api/auth/pedidos/<pk>/detalle/
    Devuelve el pedido con su pago (si existe) — para la "boletita".
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            pedido = Pedido.objects.select_related('negocio', 'cliente', 'repartidor') \
                                    .prefetch_related('detalles__producto') \
                                    .get(pk=pk, cliente=request.user)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(PedidoConPagoSerializer(pedido).data)

# ──────────────────────────────────────────
# PERFIL
# ──────────────────────────────────────────

class SubirFotoPerfilView(APIView):
    """
    POST /api/auth/perfil/foto/
    Sube o reemplaza la foto de perfil del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        if 'foto' not in request.FILES:
            return Response({'error': 'No se envió ninguna imagen.'}, status=400)

        # Borrar foto anterior si existe
        if user.foto:
            if os.path.isfile(user.foto.path):
                os.remove(user.foto.path)

        user.foto = request.FILES['foto']
        user.save()
        return Response({
            'mensaje': 'Foto actualizada correctamente.',
            'foto': request.build_absolute_uri(user.foto.url)
        })
    

# ──────────────────────────────────────────
# RECUPERACIÓN DE CONTRASEÑA
# ──────────────────────────────────────────

class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset-request/
    El usuario ingresa su email y recibe un link para resetear su contraseña.
    No requiere token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()

        if not email:
            return Response(
                {'error': 'El correo es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Respuesta genérica por seguridad (no revelamos si el email existe)
        RESPUESTA = Response(
            {'message': 'Si el correo existe, recibirás un enlace en breve.'},
            status=status.HTTP_200_OK
        )

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            return RESPUESTA

        # Invalidar tokens anteriores
        PasswordResetToken.objects.filter(user=usuario, used=False).update(used=True)

        # Crear nuevo token
        reset_token = PasswordResetToken.objects.create(user=usuario)

        # Construir el link
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token.token}"

        # Enviar email
        send_mail(
            subject='🔑 Recupera tu contraseña — LlegaYa',
            message=(
                f'Hola {usuario.nombre},\n\n'
                f'Recibimos una solicitud para restablecer tu contraseña.\n\n'
                f'Haz clic en el siguiente enlace:\n\n'
                f'{reset_link}\n\n'
                f'Este enlace expira en 15 minutos.\n\n'
                f'Si no solicitaste esto, ignora este correo.\n\n'
                f'— Equipo LlegaYa 🛵'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=False,
        )

        return RESPUESTA


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset-confirm/
    El usuario envía el token y su nueva contraseña.
    No requiere token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token_str    = request.data.get('token', '').strip()
        new_password = request.data.get('new_password', '').strip()

        if not token_str or not new_password:
            return Response(
                {'error': 'Token y nueva contraseña son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 4:
            return Response(
                {'error': 'La contraseña debe tener al menos 4 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(token=token_str)
        except (PasswordResetToken.DoesNotExist, ValueError):
            return Response(
                {'error': 'Token inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not reset_token.is_valid():
            return Response(
                {'error': 'El enlace ha expirado. Solicita uno nuevo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Actualizar contraseña
        usuario = reset_token.user
        usuario.set_password(new_password)
        usuario.save()

        # Marcar token como usado
        reset_token.used = True
        reset_token.save()

        return Response(
            {'message': 'Contraseña actualizada correctamente. Ya puedes iniciar sesión.'},
            status=status.HTTP_200_OK
        )

# ──────────────────────────────────────────
# REPARTIDOR
# ──────────────────────────────────────────

from .models import PerfilRepartidor

class PedidosDisponiblesView(APIView):
    """
    GET /api/auth/pedidos/disponibles/
    Repartidor ve pedidos en estado 'pendiente' que coincidan con su zona.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            perfil = request.user.perfil_repartidor
        except PerfilRepartidor.DoesNotExist:
            return Response({'error': 'No tienes perfil de repartidor.'}, status=403)

        if not perfil.disponible:
            return Response([])

        zona = perfil.zona_cobertura.lower().strip()

        # Pedidos pendientes cuya dirección contenga alguna palabra de la zona
        pedidos = Pedido.objects.filter(
            estado='pendiente',
            repartidor__isnull=True
        )

        # Filtrar por coincidencia de zona
        if zona:
            palabras = [p.strip() for p in zona.replace(',', ' ').split() if len(p.strip()) > 2]
            from django.db.models import Q
            filtro = Q()
            for palabra in palabras:
                filtro |= Q(direccion_entrega__icontains=palabra)
            pedidos = pedidos.filter(filtro)

        return Response(PedidoSerializer(pedidos, many=True).data)


class TomarPedidoView(APIView):
    """
    POST /api/auth/pedidos/<pk>/tomar/
    Repartidor acepta un pedido disponible.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            perfil = request.user.perfil_repartidor
        except PerfilRepartidor.DoesNotExist:
            return Response({'error': 'No tienes perfil de repartidor.'}, status=403)

        try:
            pedido = Pedido.objects.get(pk=pk, estado='pendiente', repartidor__isnull=True)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no disponible o ya fue tomado.'}, status=404)

        pedido.repartidor = request.user
        pedido.estado = 'confirmado'
        pedido.save()

        return Response(PedidoSerializer(pedido).data, status=200)


# ──────────────────────────────────────────
# CALIFICACIONES
# ──────────────────────────────────────────

class CalificarPedidoView(APIView):
    """
    POST /api/auth/pedidos/<pk>/calificar/
    El cliente califica al repartidor de su pedido.
    Requiere: ser dueño del pedido, que esté entregado/completado y sin calificar aún.
    Body: { "estrellas": 5, "comentario": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pedido = Pedido.objects.select_related('cliente', 'repartidor').get(pk=pk)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id:
            return Response(
                {'error': 'No tienes permiso para calificar este pedido.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if pedido.estado not in ('entregado', 'completado'):
            return Response(
                {'error': 'Solo puedes calificar pedidos entregados o completados.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not pedido.repartidor_id:
            return Response(
                {'error': 'Este pedido no tiene un repartidor asignado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(pedido, 'calificacion'):
            return Response(
                {'error': 'Este pedido ya fue calificado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CalificacionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        calificacion = serializer.save(pedido=pedido, repartidor=pedido.repartidor)
        return Response(CalificacionSerializer(calificacion).data, status=status.HTTP_201_CREATED)


class CalificacionPedidoView(APIView):
    """
    GET /api/auth/pedidos/<pk>/calificacion/
    Devuelve la calificación del pedido, si existe.
    Requiere: ser el cliente o el repartidor del pedido.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            pedido = Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id and pedido.repartidor_id != request.user.id:
            return Response(
                {'error': 'No tienes permiso para ver esta calificación.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            calificacion = pedido.calificacion
        except Calificacion.DoesNotExist:
            return Response(
                {'error': 'Este pedido no tiene calificación.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(CalificacionSerializer(calificacion).data)


class PromedioCalificacionesRepartidorView(APIView):
    """
    GET /api/auth/repartidor/calificaciones/promedio/
    Devuelve { promedio, total } de las calificaciones recibidas por el
    repartidor autenticado. Si no tiene calificaciones, promedio es null.
    """
    permission_classes = [IsAuthenticated, EsRepartidor]

    def get(self, request):
        from django.db.models import Avg, Count

        agregados = Calificacion.objects.filter(repartidor=request.user).aggregate(
            promedio=Avg('estrellas'), total=Count('id')
        )
        promedio = agregados['promedio']

        return Response({
            'promedio': round(promedio, 2) if promedio is not None else None,
            'total': agregados['total'],
        })


# ──────────────────────────────────────────
# PAGOS — Historial (HU15) / Distribución (HU14)
# ──────────────────────────────────────────

class HistorialPagosView(APIView):
    """
    GET /api/auth/pagos/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    Devuelve todos los pagos confirmados con su distribución de ingresos
    (comisión de plataforma, monto de comercio, monto de repartidor).
    Filtra por la fecha del pago (inclusive en ambos extremos).
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def get(self, request):
        qs = Pago.objects.select_related(
            'pedido', 'pedido__negocio', 'pedido__repartidor'
        ).order_by('-fecha')

        desde_str = request.query_params.get('desde')
        hasta_str = request.query_params.get('hasta')

        if desde_str:
            desde = parse_date(desde_str)
            if not desde:
                return Response(
                    {'error': 'Formato de fecha "desde" inválido. Usa YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            qs = qs.filter(fecha__date__gte=desde)

        if hasta_str:
            hasta = parse_date(hasta_str)
            if not hasta:
                return Response(
                    {'error': 'Formato de fecha "hasta" inválido. Usa YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            qs = qs.filter(fecha__date__lte=hasta)

        return Response(HistorialPagoSerializer(qs, many=True).data)


# ──────────────────────────────────────────
# INCIDENCIAS — Registro (HU16) / Gestión de reclamos (HU17)
# ──────────────────────────────────────────

class CrearIncidenciaView(APIView):
    """
    POST /api/auth/pedidos/<pk>/incidencias/
    El cliente reporta un problema sobre su pedido (HU16).
    Body: { "tipo": "pedido_no_llego", "descripcion": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pedido = Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id:
            return Response(
                {'error': 'No tienes permiso para reportar una incidencia sobre este pedido.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if pedido.incidencias.filter(estado__in=Incidencia.ESTADOS_ACTIVOS).exists():
            return Response(
                {'error': 'Este pedido ya tiene una incidencia activa.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = IncidenciaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        incidencia = serializer.save(pedido=pedido, cliente=request.user)
        return Response(IncidenciaSerializer(incidencia).data, status=status.HTTP_201_CREATED)


class IncidenciasListView(APIView):
    """
    GET /api/auth/incidencias/?estado=abierto
    Bandeja de soporte: todas las incidencias del sistema (HU17).
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def get(self, request):
        qs = Incidencia.objects.select_related('cliente', 'pedido').order_by('-created_at')

        estado = request.query_params.get('estado')
        if estado:
            if estado not in dict(Incidencia.ESTADOS):
                return Response(
                    {'error': f'Estado inválido. Opciones: {list(dict(Incidencia.ESTADOS).keys())}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            qs = qs.filter(estado=estado)

        return Response(IncidenciaSerializer(qs, many=True).data)


class ResponderIncidenciaView(APIView):
    """
    PUT /api/auth/incidencias/<pk>/responder/
    Soporte actualiza estado y respuesta de una incidencia en un solo request (HU17).
    Body: { "estado": "resuelto", "respuesta": "..." }
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def put(self, request, pk):
        try:
            incidencia = Incidencia.objects.get(pk=pk)
        except Incidencia.DoesNotExist:
            return Response({'error': 'Incidencia no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        estado = request.data.get('estado')
        if estado not in dict(Incidencia.ESTADOS):
            return Response(
                {'error': f'Estado inválido. Opciones: {list(dict(Incidencia.ESTADOS).keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        incidencia.estado = estado
        incidencia.respuesta = request.data.get('respuesta', incidencia.respuesta)
        incidencia.save()

        return Response(IncidenciaSerializer(incidencia).data)


# ──────────────────────────────────────────
# REPORTES — Diario (HU18) / Por comercio (HU19)
# ──────────────────────────────────────────

class ReporteDiarioView(APIView):
    """
    GET /api/auth/reportes/diario/?fecha=YYYY-MM-DD
    Reporte diario para el panel admin (HU18). Si no se envía "fecha", usa el día actual.
    Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def get(self, request):
        fecha_str = request.query_params.get('fecha')
        if fecha_str:
            fecha = parse_date(fecha_str)
            if not fecha:
                return Response(
                    {'error': 'Formato de fecha inválido. Usa YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            fecha = timezone.localdate()

        total_pedidos = Pedido.objects.filter(created_at__date=fecha).count()

        ingresos = Pago.objects.filter(fecha__date=fecha).aggregate(
            total=Sum('monto')
        )['total'] or Decimal('0.00')

        cancelaciones = Pedido.objects.filter(created_at__date=fecha, estado='cancelado').count()

        return Response({
            'fecha': fecha.isoformat(),
            'total_pedidos': total_pedidos,
            'ingresos': float(ingresos),
            'cancelaciones': cancelaciones,
        })


class ReporteNegocioView(APIView):
    """
    GET /api/auth/negocio/reporte/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    Reporte de ventas del negocio del usuario autenticado (HU19).
    Si no se envían "desde"/"hasta", usa los últimos 7 días.
    Requiere: ser dueño de un negocio.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def get(self, request):
        negocio = request.user.negocio

        hasta_str = request.query_params.get('hasta')
        if hasta_str:
            hasta = parse_date(hasta_str)
            if not hasta:
                return Response(
                    {'error': 'Formato de fecha "hasta" inválido. Usa YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            hasta = timezone.localdate()

        desde_str = request.query_params.get('desde')
        if desde_str:
            desde = parse_date(desde_str)
            if not desde:
                return Response(
                    {'error': 'Formato de fecha "desde" inválido. Usa YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            desde = hasta - timedelta(days=6)

        if desde > hasta:
            return Response(
                {'error': 'La fecha "desde" no puede ser posterior a "hasta".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if (hasta - desde).days > 366:
            return Response(
                {'error': 'El rango de fechas no puede superar 366 días.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # "ventas" = dinero realmente recibido, igual criterio que HU18: pagos confirmados.
        pagos_rango = Pago.objects.filter(
            pedido__negocio=negocio,
            fecha__date__gte=desde,
            fecha__date__lte=hasta,
        )

        ventas_totales = pagos_rango.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

        detalles = DetallePedido.objects.filter(
            pedido__in=pagos_rango.values('pedido_id')
        ).values('producto_id', 'producto__nombre').annotate(
            cantidad_vendida=Sum('cantidad'),
            ingresos=Sum(F('cantidad') * F('precio_unitario')),
        ).order_by('-cantidad_vendida')[:8]

        productos_mas_vendidos = [
            {
                'producto_id': d['producto_id'],
                'nombre': d['producto__nombre'],
                'cantidad_vendida': d['cantidad_vendida'],
                'ingresos': float(d['ingresos'] or Decimal('0.00')),
            }
            for d in detalles
        ]

        por_dia_map = {
            row['dia']: row['total']
            for row in pagos_rango.annotate(dia=TruncDate('fecha'))
                                   .values('dia')
                                   .annotate(total=Sum('monto'))
        }

        ventas_por_dia = []
        dia_actual = desde
        while dia_actual <= hasta:
            ventas_por_dia.append({
                'fecha': dia_actual.isoformat(),
                'total': float(por_dia_map.get(dia_actual) or Decimal('0.00')),
            })
            dia_actual += timedelta(days=1)

        return Response({
            'ventas_totales': float(ventas_totales),
            'productos_mas_vendidos': productos_mas_vendidos,
            'ventas_por_dia': ventas_por_dia,
        })


# ──────────────────────────────────────────
# PREDICCIÓN DE DEMANDA (HU20)
# ──────────────────────────────────────────

class PrediccionDemandaView(APIView):
    """
    GET /api/auth/predicciones/demanda/?dias_historico=14&dias_prediccion=7
    Histórico real de pedidos por día + predicción por media móvil ajustada
    por día de la semana (HU20). Requiere: rol admin.
    """
    permission_classes = [IsAuthenticated, EsAdmin]

    def get(self, request):
        try:
            dias_historico = int(request.query_params.get('dias_historico', 14))
            dias_prediccion = int(request.query_params.get('dias_prediccion', 7))
        except (TypeError, ValueError):
            return Response(
                {'error': '"dias_historico" y "dias_prediccion" deben ser números enteros.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (1 <= dias_historico <= 180):
            return Response(
                {'error': '"dias_historico" debe estar entre 1 y 180.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not (1 <= dias_prediccion <= 30):
            return Response(
                {'error': '"dias_prediccion" debe estar entre 1 y 30.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        hoy = timezone.localdate()
        inicio_historico = hoy - timedelta(days=dias_historico - 1)

        conteos_por_dia = {
            row['dia']: row['total']
            for row in Pedido.objects.filter(
                created_at__date__gte=inicio_historico,
                created_at__date__lte=hoy,
            ).annotate(dia=TruncDate('created_at')).values('dia').annotate(total=Count('id'))
        }

        historico = []
        pedidos_por_dia_semana = defaultdict(list)
        dia_actual = inicio_historico
        while dia_actual <= hoy:
            pedidos_dia = conteos_por_dia.get(dia_actual, 0)
            historico.append({'fecha': dia_actual.isoformat(), 'pedidos': pedidos_dia})
            pedidos_por_dia_semana[dia_actual.weekday()].append(pedidos_dia)
            dia_actual += timedelta(days=1)

        promedio_general = sum(h['pedidos'] for h in historico) / len(historico)
        promedio_por_dia_semana = {
            dia_semana: sum(valores) / len(valores)
            for dia_semana, valores in pedidos_por_dia_semana.items()
        }

        prediccion = []
        dia_actual = hoy + timedelta(days=1)
        for _ in range(dias_prediccion):
            estimado = promedio_por_dia_semana.get(dia_actual.weekday(), promedio_general)
            prediccion.append({'fecha': dia_actual.isoformat(), 'pedidos': round(estimado)})
            dia_actual += timedelta(days=1)

        return Response({
            'historico': historico,
            'prediccion': prediccion,
            'prediccion_manana': prediccion[0]['pedidos'],
        })