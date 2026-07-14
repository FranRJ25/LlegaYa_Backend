from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    return JsonResponse({"status": "ok", "servicio": "servicio-negocios"})


urlpatterns = [
    path("salud/", salud),
    path("api/negocios/", include("negocios.urls")),
]
