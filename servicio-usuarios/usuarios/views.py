from django.conf import settings
from django.core.mail import send_mail
from requests import request
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from core.service_client import llamar

from .cookies import NOMBRE_COOKIE_REFRESH, delete_refresh_cookie, set_refresh_cookie
from .models import PasswordResetToken, Rol, Usuario
from .serializers import (
    CustomTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UsuarioSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        refresh = data.pop("refresh")
        response = Response({"access": data["access"], "usuario": data["usuario"]}, status=status.HTTP_200_OK)
        set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(NOMBRE_COOKIE_REFRESH)
        if not refresh_token:
            return Response({"detail": "No hay refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response({"detail": "Refresh token invalido"}, status=status.HTTP_401_UNAUTHORIZED)

        data = serializer.validated_data
        response = Response({"access": data["access"]}, status=status.HTTP_200_OK)
        nuevo_refresh = data.get("refresh")
        if nuevo_refresh:
            set_refresh_cookie(response, nuevo_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get(NOMBRE_COOKIE_REFRESH)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        delete_refresh_cookie(response)
        return response


class RegisterRepartidorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        rol_obj, _ = Rol.objects.get_or_create(nombre=Rol.REPARTIDOR)

        usuario = Usuario(
            nombre=request.data["nombres"],
            apellido=request.data["apellidos"],
            email=request.data["email"],
            telefono=request.data["celular"],
            rol=rol_obj,
        )

        usuario.set_password(request.data["password"])
        usuario.save()

        respuesta = llamar(
            "POST",
            "/api/repartidores/register/",
            json={
                "usuario_id": usuario.id,
                "dni": request.data["dni"],
                "vehiculo": request.data["vehiculo"],
                "zona_cobertura": request.data.get("zona_cobertura", ""),
            },
        )

        if respuesta.status_code >= 400:
            usuario.delete()

            return Response(
                respuesta.json(),
                status=respuesta.status_code,
            )

        return Response(
            UsuarioSerializer(usuario).data,
            status=status.HTTP_201_CREATED,
        )


class PerfilView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def put(self, request):
        serializer = UsuarioSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        usuario = Usuario.objects.filter(email__iexact=email).first()
        if usuario:
            PasswordResetToken.objects.filter(user=usuario, used=False).update(used=True)
            reset_token = PasswordResetToken.objects.create(user=usuario)
            link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token.token}"
            send_mail(
                subject="Recupera tu contraseña - LlegaYa",
                message=f"Usa este enlace para restablecer tu contraseña (valido 15 min): {link}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        return Response(
            {"detail": "Si el correo existe, se enviaron instrucciones para restablecer la contraseña."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_uuid = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        reset_token = PasswordResetToken.objects.filter(token=token_uuid).first()
        if not reset_token or not reset_token.is_valid():
            return Response({"detail": "Token invalido o expirado."}, status=status.HTTP_400_BAD_REQUEST)

        usuario = reset_token.user
        usuario.set_password(password)
        usuario.save(update_fields=["password"])
        reset_token.used = True
        reset_token.save(update_fields=["used"])
        return Response({"detail": "Contraseña actualizada correctamente."}, status=status.HTTP_200_OK)
