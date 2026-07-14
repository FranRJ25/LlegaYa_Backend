from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.service_client import llamar

from .models import Negocio
from .serializers import NegocioSerializer


class MiNegocioView(APIView):
    def get(self, request):
        negocio = Negocio.objects.filter(propietario_id=request.user.id).first()
        if not negocio:
            return Response({"detail": "No tienes un negocio registrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(NegocioSerializer(negocio).data)

    def post(self, request):
        if Negocio.objects.filter(propietario_id=request.user.id).exists():
            return Response({"detail": "Ya tienes un negocio registrado."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = NegocioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(propietario_id=request.user.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request):
        negocio = Negocio.objects.filter(propietario_id=request.user.id).first()
        if not negocio:
            return Response({"detail": "No tienes un negocio registrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = NegocioSerializer(negocio, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ListaNegociosView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        negocios = Negocio.objects.filter(activo=True).order_by("nombre")
        return Response(NegocioSerializer(negocios, many=True).data)


class DetalleNegocioView(RetrieveAPIView):
    """Consulta de solo lectura, usada por otros microservicios a traves del API Gateway."""

    permission_classes = [AllowAny]
    queryset = Negocio.objects.all()
    serializer_class = NegocioSerializer


class ReporteNegocioView(APIView):
    """GET /api/negocios/mi-negocio/reporte/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    Reporte de ventas del negocio del usuario autenticado. Delega el calculo a
    servicio-pedidos (a traves del Gateway), que es quien tiene los datos de
    pedidos y pagos."""

    def get(self, request):
        negocio = Negocio.objects.filter(propietario_id=request.user.id).first()
        if not negocio:
            return Response({"detail": "No tienes un negocio registrado."}, status=status.HTTP_404_NOT_FOUND)

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        headers = {"Authorization": auth_header} if auth_header else None
        params = {"negocio_id": negocio.id}
        if request.query_params.get("desde"):
            params["desde"] = request.query_params["desde"]
        if request.query_params.get("hasta"):
            params["hasta"] = request.query_params["hasta"]

        try:
            resp = llamar("GET", "/api/pedidos/reportes/negocio/", headers=headers, params=params)
        except Exception:
            return Response({"detail": "servicio-pedidos no disponible"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(resp.json(), status=resp.status_code)
