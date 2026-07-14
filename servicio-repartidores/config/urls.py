from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    return JsonResponse({"status": "ok", "servicio": "servicio-repartidores"})


urlpatterns = [
    path("salud/", salud),
    path("api/repartidores/", include("repartidores.urls")),
]
