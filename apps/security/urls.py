from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, RegisterView, LogoutView, PerfilView,
    ListaUsuariosView, CambiarRolView, ToggleEstadoUsuarioView,
    MiNegocioView, ListaNegociosView,
    ProductosNegocioView,
    MisPedidosView, AsignarRepartidorView, ActualizarEstadoPedidoView,
    SubirFotoPerfilView,
    PasswordResetRequestView, PasswordResetConfirmView,
)

urlpatterns = [
    #Auth
    path('login/',    LoginView.as_view(),    name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('refresh/',  TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/',   LogoutView.as_view(),   name='logout'),
    path('perfil/',   PerfilView.as_view(),   name='perfil'),
    #Admin
    path('admin/usuarios/',              ListaUsuariosView.as_view(),  name='lista-usuarios'),
    path('admin/usuarios/<int:pk>/rol/', CambiarRolView.as_view(),     name='cambiar-rol'),
    path('admin/usuarios/<int:pk>/estado/', ToggleEstadoUsuarioView.as_view(), name='toggle-estado'),
    #Negocios
    path('negocio/',           MiNegocioView.as_view(),        name='mi-negocio'),
    path('negocios/',          ListaNegociosView.as_view(),    name='lista-negocios'),
    path('negocio/productos/', ProductosNegocioView.as_view(), name='productos-negocio'),
    #Pedidos
    path('pedidos/',                        MisPedidosView.as_view(),             name='mis-pedidos'),
    path('pedidos/<int:pk>/asignar/',       AsignarRepartidorView.as_view(),      name='asignar-repartidor'),
    path('pedidos/<int:pk>/estado/',        ActualizarEstadoPedidoView.as_view(), name='actualizar-estado'),
    #Perfil
    path('perfil/foto/', SubirFotoPerfilView.as_view(), name='subir-foto-perfil'),
    #Recuperación de contraseña
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]