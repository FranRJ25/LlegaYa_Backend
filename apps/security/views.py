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
import os

from .models import Usuario, Rol, Negocio, Producto, Pedido, DetallePedido, PasswordResetToken
from .serializers import (
    RegisterSerializer, UsuarioSerializer,
    CustomTokenObtainPairSerializer,
    NegocioSerializer, NegocioCreateSerializer,
    ProductoSerializer, PedidoSerializer,
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
    Crea un usuario nuevo. Por defecto se le asigna rol 'cliente'.
    No requiere token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            # Si no mandaron rol, asignamos 'cliente' por defecto
            if not usuario.rol:
                try:
                    usuario.rol = Rol.objects.get(nombre='cliente')
                    usuario.save()
                except Rol.DoesNotExist:
                    pass
            return Response(
                {'mensaje': 'Usuario registrado correctamente', 'usuario': UsuarioSerializer(usuario).data},
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

class ProductosNegocioView(APIView):
    """
    GET  /api/auth/negocio/productos/          → ver mis productos
    POST /api/auth/negocio/productos/          → crear producto
    Requiere: tener un negocio registrado.
    """
    permission_classes = [IsAuthenticated, EsPropietarioDeNegocio]

    def get(self, request):
        productos = Producto.objects.filter(negocio=request.user.negocio)
        return Response(ProductoSerializer(productos, many=True).data)

    def post(self, request):
        serializer = ProductoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(negocio=request.user.negocio)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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