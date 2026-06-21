from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal, InvalidOperation
import os

from .models import Usuario, Rol, Negocio, Producto, Pedido, DetallePedido, PasswordResetToken, HistorialCambioProducto, PerfilRepartidor
from .serializers import (
    RegisterSerializer, UsuarioSerializer,
    CustomTokenObtainPairSerializer,
    NegocioSerializer, NegocioCreateSerializer,
    ProductoSerializer, PedidoSerializer,
    HistorialCambioSerializer, PerfilRepartidorSerializer
)
from .permissions import EsAdmin, EsCliente, EsRepartidor, EsPropietarioDeNegocio, EsAdminORepartidor


# ──────────────────────────────────────────
# AUTENTICACIÓN
# ──────────────────────────────────────────

class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Devuelve access token, refresh token y datos del usuario.
    No requiere token (es el endpoint para obtenerlo).
    """
    serializer_class   = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


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
    Invalida el refresh token.
    Requiere: estar autenticado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'mensaje': 'Sesión cerrada correctamente'})
        except Exception:
            return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)


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

        if rol == 'admin':
            pedidos = Pedido.objects.select_related('cliente', 'negocio', 'repartidor').all()
        elif rol == 'repartidor':
            pedidos = Pedido.objects.filter(repartidor=request.user)
        else:
            pedidos = Pedido.objects.filter(cliente=request.user)

        return Response(PedidoSerializer(pedidos, many=True).data)


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