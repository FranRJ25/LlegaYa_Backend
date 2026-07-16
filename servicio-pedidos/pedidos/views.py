from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import EsAdmin, EsAdminORepartidor
from core.service_client import obtener_mi_negocio, obtener_negocio, obtener_producto

from .models import Calificacion, DetallePedido, Incidencia, Pago, Pedido
from .serializers import (
    CalificacionSerializer,
    CrearPedidoSerializer,
    HistorialPagoSerializer,
    IncidenciaSerializer,
    PedidoConPagoSerializer,
    PedidoSerializer,
)


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


class ListaPedidosNegocioView(APIView):

    def get(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION")
        negocio = obtener_mi_negocio(auth_header)
        if not negocio:
            return Response({"detail": "No tienes un negocio registrado."}, status=status.HTTP_404_NOT_FOUND)
        pedidos = Pedido.objects.filter(negocio_id=negocio["id"]).order_by("-created_at")
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


def _centavos(valor):
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calcular_distribucion_pago(negocio, monto_total):
    """HU14 - la comision de plataforma depende del negocio (comision_porcentaje,
    obtenido de servicio-negocios); la del repartidor es un % fijo de plataforma."""
    comision_negocio_pct = Decimal(str(negocio["comision_porcentaje"]))
    comision_repartidor_pct = settings.REPARTIDOR_COMISION_PORCENTAJE

    comision_plataforma = _centavos(monto_total * comision_negocio_pct / Decimal("100"))
    monto_repartidor = _centavos(monto_total * comision_repartidor_pct / Decimal("100"))
    monto_comercio = monto_total - comision_plataforma - monto_repartidor

    return comision_plataforma, monto_comercio, monto_repartidor


class PagarPedidoView(APIView):
    """POST /api/pedidos/<pk>/pagar/  Body: { "metodo": "yape" }"""

    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk, cliente_id=request.user.id).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(pedido, "pago"):
            return Response({"detail": "Este pedido ya fue pagado."}, status=status.HTTP_400_BAD_REQUEST)

        metodo = request.data.get("metodo", "tarjeta")
        if metodo not in dict(Pago.METODOS):
            return Response({"detail": "Metodo de pago invalido."}, status=status.HTTP_400_BAD_REQUEST)

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        negocio = obtener_negocio(pedido.negocio_id, auth_header)
        if not negocio:
            return Response({"detail": "servicio-negocios no disponible"}, status=status.HTTP_502_BAD_GATEWAY)

        comision_plataforma, monto_comercio, monto_repartidor = _calcular_distribucion_pago(
            negocio, pedido.total
        )

        pago = Pago.objects.create(
            pedido=pedido,
            monto=pedido.total,
            metodo=metodo,
            comision_plataforma=comision_plataforma,
            monto_comercio=monto_comercio,
            monto_repartidor=monto_repartidor,
        )

        return Response(
            {"mensaje": "Pago registrado correctamente.", "pedido": PedidoConPagoSerializer(pedido).data},
            status=status.HTTP_201_CREATED,
        )


class DetallePedidoConPagoView(APIView):
    """GET /api/pedidos/<pk>/detalle/  Devuelve el pedido con su pago (si existe)."""

    def get(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk, cliente_id=request.user.id).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PedidoConPagoSerializer(pedido).data)


class HistorialPagosView(APIView):
    """GET /api/pedidos/pagos/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD"""

    permission_classes = [EsAdmin]

    def get(self, request):
        qs = Pago.objects.order_by("-fecha")

        desde_str = request.query_params.get("desde")
        if desde_str:
            desde = parse_date(desde_str)
            if not desde:
                return Response({"detail": "Formato de fecha 'desde' invalido."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fecha__date__gte=desde)

        hasta_str = request.query_params.get("hasta")
        if hasta_str:
            hasta = parse_date(hasta_str)
            if not hasta:
                return Response({"detail": "Formato de fecha 'hasta' invalido."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(fecha__date__lte=hasta)

        return Response(HistorialPagoSerializer(qs, many=True).data)


class CalificarPedidoView(APIView):
    """POST /api/pedidos/<pk>/calificar/  Body: { "estrellas": 5, "comentario": "..." }"""

    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id:
            return Response(
                {"detail": "No tienes permiso para calificar este pedido."}, status=status.HTTP_403_FORBIDDEN
            )

        if pedido.estado not in ("entregado", "completado"):
            return Response(
                {"detail": "Solo puedes calificar pedidos entregados o completados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not pedido.repartidor_id:
            return Response(
                {"detail": "Este pedido no tiene un repartidor asignado."}, status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(pedido, "calificacion"):
            return Response({"detail": "Este pedido ya fue calificado."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CalificacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        calificacion = serializer.save(pedido=pedido, repartidor_id=pedido.repartidor_id)
        return Response(CalificacionSerializer(calificacion).data, status=status.HTTP_201_CREATED)


class CalificacionPedidoView(APIView):
    """GET /api/pedidos/<pk>/calificacion/"""

    def get(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id and pedido.repartidor_id != request.user.id:
            return Response(
                {"detail": "No tienes permiso para ver esta calificacion."}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            calificacion = pedido.calificacion
        except Calificacion.DoesNotExist:
            return Response({"detail": "Este pedido no tiene calificacion."}, status=status.HTTP_404_NOT_FOUND)

        return Response(CalificacionSerializer(calificacion).data)


class PromedioCalificacionesRepartidorView(APIView):
    """GET /api/pedidos/calificaciones/promedio/?repartidor_id=123
    Usado por servicio-repartidores (a traves del API Gateway)."""

    def get(self, request):
        repartidor_id = request.query_params.get("repartidor_id")
        if not repartidor_id:
            return Response({"detail": "repartidor_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        agregados = Calificacion.objects.filter(repartidor_id=repartidor_id).aggregate(
            promedio=Avg("estrellas"), total=Count("id")
        )
        promedio = agregados["promedio"]

        return Response({
            "promedio": round(promedio, 2) if promedio is not None else None,
            "total": agregados["total"],
        })


class CrearIncidenciaView(APIView):
    """POST /api/pedidos/<pk>/incidencias/  Body: { "tipo": "...", "descripcion": "..." }"""

    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if not pedido:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pedido.cliente_id != request.user.id:
            return Response(
                {"detail": "No tienes permiso para reportar una incidencia sobre este pedido."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if pedido.incidencias.filter(estado__in=Incidencia.ESTADOS_ACTIVOS).exists():
            return Response(
                {"detail": "Este pedido ya tiene una incidencia activa."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = IncidenciaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incidencia = serializer.save(pedido=pedido, cliente_id=request.user.id)
        return Response(IncidenciaSerializer(incidencia).data, status=status.HTTP_201_CREATED)


class IncidenciasListView(APIView):
    """GET /api/pedidos/incidencias/?estado=abierto"""

    permission_classes = [EsAdmin]

    def get(self, request):
        qs = Incidencia.objects.order_by("-created_at")

        estado = request.query_params.get("estado")
        if estado:
            if estado not in dict(Incidencia.ESTADOS):
                return Response(
                    {"detail": f"Estado invalido. Opciones: {list(dict(Incidencia.ESTADOS).keys())}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(estado=estado)

        return Response(IncidenciaSerializer(qs, many=True).data)


class ResponderIncidenciaView(APIView):
    """PUT /api/pedidos/incidencias/<pk>/responder/  Body: { "estado": "resuelto", "respuesta": "..." }"""

    permission_classes = [EsAdmin]

    def put(self, request, pk):
        incidencia = Incidencia.objects.filter(pk=pk).first()
        if not incidencia:
            return Response({"detail": "Incidencia no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        estado = request.data.get("estado")
        if estado not in dict(Incidencia.ESTADOS):
            return Response(
                {"detail": f"Estado invalido. Opciones: {list(dict(Incidencia.ESTADOS).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        incidencia.estado = estado
        incidencia.respuesta = request.data.get("respuesta", incidencia.respuesta)
        incidencia.save()

        return Response(IncidenciaSerializer(incidencia).data)


class ReporteDiarioView(APIView):
    """GET /api/pedidos/reportes/diario/?fecha=YYYY-MM-DD"""

    permission_classes = [EsAdmin]

    def get(self, request):
        fecha_str = request.query_params.get("fecha")
        if fecha_str:
            fecha = parse_date(fecha_str)
            if not fecha:
                return Response({"detail": "Formato de fecha invalido."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            fecha = timezone.localdate()

        total_pedidos = Pedido.objects.filter(created_at__date=fecha).count()
        ingresos = Pago.objects.filter(fecha__date=fecha).aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
        cancelaciones = Pedido.objects.filter(created_at__date=fecha, estado="cancelado").count()

        return Response({
            "fecha": fecha.isoformat(),
            "total_pedidos": total_pedidos,
            "ingresos": float(ingresos),
            "cancelaciones": cancelaciones,
        })


class ReporteNegocioDatosView(APIView):
    """GET /api/pedidos/reportes/negocio/?negocio_id=1&desde=&hasta=
    Usado por servicio-negocios (a traves del API Gateway); la verificacion de que
    el usuario autenticado es dueno de ese negocio ya la hizo servicio-negocios."""

    def get(self, request):
        negocio_id = request.query_params.get("negocio_id")
        if not negocio_id:
            return Response({"detail": "negocio_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        hasta_str = request.query_params.get("hasta")
        if hasta_str:
            hasta = parse_date(hasta_str)
            if not hasta:
                return Response({"detail": "Formato de fecha 'hasta' invalido."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            hasta = timezone.localdate()

        desde_str = request.query_params.get("desde")
        if desde_str:
            desde = parse_date(desde_str)
            if not desde:
                return Response({"detail": "Formato de fecha 'desde' invalido."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            desde = hasta - timedelta(days=6)

        if desde > hasta:
            return Response(
                {"detail": "La fecha 'desde' no puede ser posterior a 'hasta'."}, status=status.HTTP_400_BAD_REQUEST
            )
        if (hasta - desde).days > 366:
            return Response(
                {"detail": "El rango de fechas no puede superar 366 dias."}, status=status.HTTP_400_BAD_REQUEST
            )

        pagos_rango = Pago.objects.filter(
            pedido__negocio_id=negocio_id, fecha__date__gte=desde, fecha__date__lte=hasta
        )

        ventas_totales = pagos_rango.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")

        detalles = DetallePedido.objects.filter(
            pedido__in=pagos_rango.values("pedido_id")
        ).values("producto_id", "nombre_producto").annotate(
            cantidad_vendida=Sum("cantidad"),
            ingresos=Sum(F("cantidad") * F("precio_unitario")),
        ).order_by("-cantidad_vendida")[:8]

        productos_mas_vendidos = [
            {
                "producto_id": d["producto_id"],
                "nombre": d["nombre_producto"],
                "cantidad_vendida": d["cantidad_vendida"],
                "ingresos": float(d["ingresos"] or Decimal("0.00")),
            }
            for d in detalles
        ]

        por_dia_map = {
            row["dia"]: row["total"]
            for row in pagos_rango.annotate(dia=TruncDate("fecha")).values("dia").annotate(total=Sum("monto"))
        }

        ventas_por_dia = []
        dia_actual = desde
        while dia_actual <= hasta:
            ventas_por_dia.append({
                "fecha": dia_actual.isoformat(),
                "total": float(por_dia_map.get(dia_actual) or Decimal("0.00")),
            })
            dia_actual += timedelta(days=1)

        return Response({
            "ventas_totales": float(ventas_totales),
            "productos_mas_vendidos": productos_mas_vendidos,
            "ventas_por_dia": ventas_por_dia,
        })


class PrediccionDemandaView(APIView):
    """GET /api/pedidos/predicciones/demanda/?dias_historico=14&dias_prediccion=7"""

    permission_classes = [EsAdmin]

    def get(self, request):
        try:
            dias_historico = int(request.query_params.get("dias_historico", 14))
            dias_prediccion = int(request.query_params.get("dias_prediccion", 7))
        except (TypeError, ValueError):
            return Response(
                {"detail": "'dias_historico' y 'dias_prediccion' deben ser numeros enteros."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (1 <= dias_historico <= 180):
            return Response({"detail": "'dias_historico' debe estar entre 1 y 180."}, status=status.HTTP_400_BAD_REQUEST)
        if not (1 <= dias_prediccion <= 30):
            return Response({"detail": "'dias_prediccion' debe estar entre 1 y 30."}, status=status.HTTP_400_BAD_REQUEST)

        hoy = timezone.localdate()
        inicio_historico = hoy - timedelta(days=dias_historico - 1)

        conteos_por_dia = {
            row["dia"]: row["total"]
            for row in Pedido.objects.filter(
                created_at__date__gte=inicio_historico, created_at__date__lte=hoy
            ).annotate(dia=TruncDate("created_at")).values("dia").annotate(total=Count("id"))
        }

        historico = []
        pedidos_por_dia_semana = defaultdict(list)
        dia_actual = inicio_historico
        while dia_actual <= hoy:
            pedidos_dia = conteos_por_dia.get(dia_actual, 0)
            historico.append({"fecha": dia_actual.isoformat(), "pedidos": pedidos_dia})
            pedidos_por_dia_semana[dia_actual.weekday()].append(pedidos_dia)
            dia_actual += timedelta(days=1)

        promedio_general = sum(h["pedidos"] for h in historico) / len(historico)
        promedio_por_dia_semana = {
            dia_semana: sum(valores) / len(valores)
            for dia_semana, valores in pedidos_por_dia_semana.items()
        }

        prediccion = []
        dia_actual = hoy + timedelta(days=1)
        for _ in range(dias_prediccion):
            estimado = promedio_por_dia_semana.get(dia_actual.weekday(), promedio_general)
            prediccion.append({"fecha": dia_actual.isoformat(), "pedidos": round(estimado)})
            dia_actual += timedelta(days=1)

        return Response({
            "historico": historico,
            "prediccion": prediccion,
            "prediccion_manana": prediccion[0]["pedidos"],
        })
