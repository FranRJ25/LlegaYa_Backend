from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    return JsonResponse({"status": "ok", "servicio": "servicio-productos"})


urlpatterns = [
    path("salud/", salud),
    path("api/productos/", include("productos.urls")),
]
