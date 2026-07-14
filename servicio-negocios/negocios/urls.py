from django.urls import path

from .views import DetalleNegocioView, ListaNegociosView, MiNegocioView

urlpatterns = [
    path("mi-negocio/", MiNegocioView.as_view(), name="negocios-mi-negocio"),
    path("lista/", ListaNegociosView.as_view(), name="negocios-lista"),
    path("<int:pk>/", DetalleNegocioView.as_view(), name="negocios-detalle"),
]
