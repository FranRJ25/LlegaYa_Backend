from django.conf import settings
from mongoengine.errors import NotUniqueError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from core.permissions import EsRepartidor
from core.service_client import llamar

from .documents import PerfilRepartidor
from .serializers import PerfilRepartidorSerializer


class MiPerfilRepartidorView(APIView):
    permission_classes = [EsRepartidor]

    def get(self, request):
        perfil = PerfilRepartidor.objects(usuario_id=request.user.id).first()
        if not perfil:
            return Response({"detail": "No tienes un perfil de repartidor."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PerfilRepartidorSerializer(perfil).data)

    def post(self, request):
        if PerfilRepartidor.objects(usuario_id=request.user.id).first():
            return Response({"detail": "Ya tienes un perfil de repartidor."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = PerfilRepartidorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            perfil = PerfilRepartidor(usuario_id=request.user.id, **serializer.validated_data).save()
        except NotUniqueError:
            return Response({"detail": "Ya tienes un perfil de repartidor."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PerfilRepartidorSerializer(perfil).data, status=status.HTTP_201_CREATED)

    def put(self, request):
        perfil = PerfilRepartidor.objects(usuario_id=request.user.id).first()
        if not perfil:
            return Response({"detail": "No tienes un perfil de repartidor."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PerfilRepartidorSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for campo, valor in serializer.validated_data.items():
            setattr(perfil, campo, valor)
        perfil.save()
        return Response(PerfilRepartidorSerializer(perfil).data)


class ToggleDisponibilidadRepartidorView(APIView):
    permission_classes = [EsRepartidor]

    def patch(self, request):
        perfil = PerfilRepartidor.objects(usuario_id=request.user.id).first()
        if not perfil:
            return Response({"detail": "No tienes un perfil de repartidor."}, status=status.HTTP_404_NOT_FOUND)
        perfil.disponible = not perfil.disponible
        perfil.save()
        return Response(PerfilRepartidorSerializer(perfil).data)


class PedidosDisponiblesView(APIView):
    permission_classes = [EsRepartidor]

    def get(self, request):
        perfil = PerfilRepartidor.objects(usuario_id=request.user.id).first()
        if not perfil or not perfil.disponible:
            return Response([])

        palabras = [
            palabra for palabra in perfil.zona_cobertura.split()
            if len(palabra) > settings.ZONA_MIN_PALABRA_LARGO
        ]

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        headers = {"Authorization": auth_header} if auth_header else None
        params = [("palabra", palabra) for palabra in palabras]
        try:
            resp = llamar("GET", "/api/pedidos/disponibles/", headers=headers, params=params)
        except Exception:
            return Response({"detail": "servicio-pedidos no disponible"}, status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code != 200:
            return Response({"detail": "no se pudo consultar pedidos disponibles"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(resp.json())


class TomarPedidoView(APIView):
    permission_classes = [EsRepartidor]

    def post(self, request, pedido_id):
        perfil = PerfilRepartidor.objects(usuario_id=request.user.id).first()
        if not perfil or not perfil.disponible:
            return Response(
                {"detail": "Debes tener un perfil de repartidor disponible para tomar pedidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        headers = {"Authorization": auth_header} if auth_header else None
        try:
            resp = llamar(
                "PATCH",
                f"/api/pedidos/{pedido_id}/asignar-repartidor/",
                headers=headers,
                json={"repartidor_id": request.user.id},
            )
        except Exception:
            return Response({"detail": "servicio-pedidos no disponible"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(resp.json(), status=resp.status_code)


class PromedioCalificacionesRepartidorView(APIView):
    """GET /api/repartidores/calificaciones/promedio/
    Devuelve { promedio, total } de las calificaciones recibidas por el
    repartidor autenticado. Delega el calculo a servicio-pedidos, que es
    quien tiene los datos de calificaciones."""

    permission_classes = [EsRepartidor]

    def get(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        headers = {"Authorization": auth_header} if auth_header else None
        try:
            resp = llamar(
                "GET",
                "/api/pedidos/calificaciones/promedio/",
                headers=headers,
                params={"repartidor_id": request.user.id},
            )
        except Exception:
            return Response({"detail": "servicio-pedidos no disponible"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(resp.json(), status=resp.status_code)


class RegisterRepartidorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        usuario_id = request.data.get("usuario_id")

        if not usuario_id:
            return Response(
                {"detail": "usuario_id es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if PerfilRepartidor.objects(usuario_id=usuario_id).first():
            return Response(
                {"detail": "El perfil ya existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PerfilRepartidorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        perfil = PerfilRepartidor(
            usuario_id=usuario_id,
            **serializer.validated_data
        ).save()

        return Response(
            PerfilRepartidorSerializer(perfil).data,
            status=status.HTTP_201_CREATED,
        )