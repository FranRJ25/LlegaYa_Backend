from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import EsAdminORepartidor
from core.service_client import obtener_producto

from .models import DetallePedido, Pedido
from .serializers import CrearPedidoSerializer, PedidoSerializer


class CrearPedidoView(APIView):
    def post(self, request):
        serializer = CrearPedidoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        direccion_entrega = serializer.validated_data["direccion_entrega"]
        items = serializer.validated_data["items"]
        auth_header = request.META.get("HTTP_AUTHORIZATION")

        productos_por_id = {}
        for item in items:
            producto = obtener_producto(item["producto_id"], auth_header)
            if not producto:
                return Response(
                    {"detail": f"Producto {item['producto_id']} no encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not producto.get("disponible"):
                return Response(
                    {"detail": f"El producto '{producto.get('nombre')}' no esta disponible."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            productos_por_id[item["producto_id"]] = producto

        items_por_negocio = defaultdict(list)
        for item in items:
            producto = productos_por_id[item["producto_id"]]
            items_por_negocio[producto["negocio_id"]].append((item, producto))

        pedidos_creados = []
        with transaction.atomic():
            for negocio_id, items_negocio in items_por_negocio.items():
                total = sum(
                    Decimal(str(producto["precio"])) * item["cantidad"] for item, producto in items_negocio
                )
                pedido = Pedido.objects.create(
                    cliente_id=request.user.id,
                    negocio_id=negocio_id,
                    direccion_entrega=direccion_entrega,
                    total=total,
                )
                for item, producto in items_negocio:
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto_id=item["producto_id"],
                        nombre_producto=producto.get("nombre", ""),
                        cantidad=item["cantidad"],
                        precio_unitario=Decimal(str(producto["precio"])),
                    )
                pedidos_creados.append(pedido)

        return Response(
            PedidoSerializer(pedidos_creados, many=True).data, status=status.HTTP_201_CREATED
        )


class ListaMisPedidosView(APIView):
    def get(self, request):
        pedidos = Pedido.objects.filter(cliente_id=request.user.id).order_by("-created_at")
        return Response(PedidoSerializer(pedidos, many=True).data)


class DetallePedidoView(APIView):
    def get(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PedidoSerializer(pedido).data)


class CancelarPedidoView(APIView):
    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if pedido.estado != "pendiente":
            return Response(
                {"detail": "Solo se pueden cancelar pedidos pendientes."}, status=status.HTTP_400_BAD_REQUEST
            )
        pedido.estado = "cancelado"
        pedido.motivo_cancelacion = request.data.get("motivo_cancelacion", "")
        pedido.save(update_fields=["estado", "motivo_cancelacion"])
        return Response(PedidoSerializer(pedido).data)


class CompletarPedidoView(APIView):
    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if pedido.estado not in ("confirmado", "en_camino"):
            return Response(
                {"detail": "El pedido no esta en un estado que se pueda completar."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pedido.estado = "completado"
        pedido.save(update_fields=["estado"])
        return Response(PedidoSerializer(pedido).data)


class PedidosDisponiblesView(APIView):
    """Usado por servicio-repartidores (a traves del API Gateway) para listar pedidos
    pendientes sin repartidor asignado, filtrados por palabras de la zona de cobertura."""

    permission_classes = [EsAdminORepartidor]

    def get(self, request):
        pedidos = Pedido.objects.filter(estado="pendiente", repartidor_id__isnull=True)
        palabras = request.query_params.getlist("palabra")
        if palabras:
            filtro = Q()
            for palabra in palabras:
                filtro |= Q(direccion_entrega__icontains=palabra)
            pedidos = pedidos.filter(filtro)
        return Response(PedidoSerializer(pedidos.order_by("-created_at"), many=True).data)


class AsignarRepartidorView(APIView):
    """Usado por servicio-repartidores (a traves del API Gateway) para autoasignarse un
    pedido de forma atomica, evitando que dos repartidores tomen el mismo pedido."""

    permission_classes = [EsAdminORepartidor]

    def patch(self, request, pk):
        repartidor_id = request.data.get("repartidor_id")
        if not repartidor_id:
            return Response({"detail": "repartidor_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        filas_actualizadas = Pedido.objects.filter(
            pk=pk, estado="pendiente", repartidor_id__isnull=True
        ).update(estado="confirmado", repartidor_id=repartidor_id)

        if filas_actualizadas == 0:
            return Response(
                {"detail": "El pedido ya no esta disponible."}, status=status.HTTP_409_CONFLICT
            )

        pedido = Pedido.objects.get(pk=pk)
        return Response(PedidoSerializer(pedido).data)
