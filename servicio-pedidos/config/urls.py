from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    return JsonResponse({"status": "ok", "servicio": "servicio-pedidos"})


urlpatterns = [
    path("salud/", salud),
    path("api/pedidos/", include("pedidos.urls")),
]
