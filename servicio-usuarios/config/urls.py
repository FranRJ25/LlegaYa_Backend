from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    return JsonResponse({"status": "ok", "servicio": "servicio-usuarios"})


urlpatterns = [
    path("salud/", salud),
    path("api/usuarios/", include("usuarios.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
