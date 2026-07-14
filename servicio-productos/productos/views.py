from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.service_client import obtener_negocio

from .models import HistorialCambioProducto, Producto
from .serializers import HistorialCambioProductoSerializer, ProductoSerializer


def _registrar_cambio(producto, usuario_id, tipo_cambio, valor_anterior="", valor_nuevo="", comentario=""):
    HistorialCambioProducto.objects.create(
        producto=producto,
        usuario_id=usuario_id,
        tipo_cambio=tipo_cambio,
        valor_anterior=str(valor_anterior),
        valor_nuevo=str(valor_nuevo),
        comentario=comentario,
    )


def _es_propietario_del_negocio(negocio_id, request):
    negocio = obtener_negocio(negocio_id, request.META.get("HTTP_AUTHORIZATION"))
    print(f"DEBUG negocio: {negocio}")
    print(f"DEBUG request.user.id: {request.user.id} (tipo: {type(request.user.id)})")
    print(f"DEBUG propietario_id: {negocio.get('propietario_id') if negocio else None} (tipo: {type(negocio.get('propietario_id')) if negocio else None})")
    print(f"DEBUG coincide: {negocio.get('propietario_id') == request.user.id if negocio else False}")
    return bool(negocio and negocio.get("propietario_id") == request.user.id)


class ListaProductosView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        negocio_id = request.query_params.get("negocio_id")
        productos = Producto.objects.all()
        if negocio_id:
            productos = productos.filter(negocio_id=negocio_id)
        return Response(ProductoSerializer(productos.order_by("nombre"), many=True).data)


class CrearProductoView(APIView):
    def post(self, request):
        negocio_id = request.data.get("negocio_id")
        if not negocio_id:
            return Response({"detail": "negocio_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)
        if not _es_propietario_del_negocio(negocio_id, request):
            return Response({"detail": "No eres propietario de ese negocio."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProductoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        producto = serializer.save(negocio_id=negocio_id)
        _registrar_cambio(producto, request.user.id, "creacion", valor_nuevo=producto.nombre)
        return Response(ProductoSerializer(producto).data, status=status.HTTP_201_CREATED)


class DetalleProductoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        producto = Producto.objects.filter(pk=pk).first()
        if not producto:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProductoSerializer(producto).data)


class ToggleDisponibilidadProductoView(APIView):
    def patch(self, request, pk):
        producto = Producto.objects.filter(pk=pk).first()
        if not producto:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if not _es_propietario_del_negocio(producto.negocio_id, request):
            return Response({"detail": "No eres propietario de ese negocio."}, status=status.HTTP_403_FORBIDDEN)

        valor_anterior = producto.disponible
        producto.disponible = not producto.disponible
        producto.save(update_fields=["disponible", "updated_at"])
        _registrar_cambio(producto, request.user.id, "disponible", valor_anterior, producto.disponible)
        return Response(ProductoSerializer(producto).data)


class ActualizarPrecioProductoView(APIView):
    def patch(self, request, pk):
        producto = Producto.objects.filter(pk=pk).first()
        if not producto:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if not _es_propietario_del_negocio(producto.negocio_id, request):
            return Response({"detail": "No eres propietario de ese negocio."}, status=status.HTTP_403_FORBIDDEN)

        try:
            nuevo_precio = Decimal(str(request.data.get("precio")))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Precio invalido."}, status=status.HTTP_400_BAD_REQUEST)
        if nuevo_precio <= 0:
            return Response({"detail": "El precio debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)

        if nuevo_precio != producto.precio:
            valor_anterior = producto.precio
            producto.precio = nuevo_precio
            producto.save(update_fields=["precio", "updated_at"])
            _registrar_cambio(producto, request.user.id, "precio", valor_anterior, nuevo_precio)
        return Response(ProductoSerializer(producto).data)


class HistorialProductoView(APIView):
    def get(self, request, pk):
        historial = HistorialCambioProducto.objects.filter(producto_id=pk)
        tipo = request.query_params.get("tipo")
        if tipo:
            historial = historial.filter(tipo_cambio=tipo)
        return Response(HistorialCambioProductoSerializer(historial, many=True).data)
