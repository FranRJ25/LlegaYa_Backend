from django.urls import path
from .views import (
    LoginView, RegisterView, LogoutView, PerfilView, SubirFotoPerfilView,
    PasswordResetRequestView, PasswordResetConfirmView,
    ListaUsuariosView, CambiarRolView, ToggleEstadoUsuarioView,
    MiNegocioView, ListaNegociosView,
    ProductosNegocioView, ProductoDetalleView,
    ToggleDisponibilidadProductoView, ActualizarPrecioProductoView,
    HistorialProductoView, HistorialCatalogoView,
    MisPedidosView, AsignarRepartidorView, ActualizarEstadoPedidoView,
    ProductosPublicosView, CrearPedidoView,
    CancelarPedidoView, CompletarPedidoView, PerfilRepartidorView,
    RegisterRepartidorView, CookieTokenRefreshView,
)

urlpatterns = [
    # Auth 
    path('login/',          LoginView.as_view(),             name='login'),
    path('register/',       RegisterView.as_view(),          name='register'),
    path('token/refresh/',  CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/',         LogoutView.as_view(),            name='logout'),
    # Perfil 
    path('perfil/',      PerfilView.as_view(),          name='perfil'),
    path('perfil/foto/', SubirFotoPerfilView.as_view(), name='subir-foto-perfil'),
    # Recuperación de contraseña 
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    # Admin 
    path('admin/usuarios/',                 ListaUsuariosView.as_view(),       name='lista-usuarios'),
    path('admin/usuarios/<int:pk>/rol/',    CambiarRolView.as_view(),          name='cambiar-rol'),
    path('admin/usuarios/<int:pk>/estado/', ToggleEstadoUsuarioView.as_view(), name='toggle-estado'),
    # Negocios 
    path('negocio/',  MiNegocioView.as_view(),       name='mi-negocio'),
    path('negocios/', ListaNegociosView.as_view(),   name='lista-negocios'),
    # Productos / Catálogo
    path('negocio/productos/',                            ProductosNegocioView.as_view(),             name='productos-negocio'),
    path('negocio/productos/<int:pk>/',                   ProductoDetalleView.as_view(),              name='producto-detalle'),
    path('negocio/productos/<int:pk>/precio/',            ActualizarPrecioProductoView.as_view(),     name='producto-precio'),
    path('negocio/productos/<int:pk>/disponibilidad/',    ToggleDisponibilidadProductoView.as_view(), name='producto-disponibilidad'),
    path('negocio/productos/<int:pk>/historial/',         HistorialProductoView.as_view(),            name='producto-historial'),
    path('negocio/catalogo/historial/',                   HistorialCatalogoView.as_view(),            name='catalogo-historial'),
    # Pedidos 
    path('pedidos/',                    MisPedidosView.as_view(),             name='mis-pedidos'),
    path('pedidos/crear/',               CrearPedidoView.as_view(),       name='crear-pedido'),
    path('pedidos/<int:pk>/asignar/',   AsignarRepartidorView.as_view(),      name='asignar-repartidor'),
    path('pedidos/<int:pk>/estado/',    ActualizarEstadoPedidoView.as_view(), name='actualizar-estado'),
    path('pedidos/<int:pk>/cancelar/',       CancelarPedidoView.as_view(),         name='cancelar-pedido'),
    path('pedidos/<int:pk>/completar/',      CompletarPedidoView.as_view(),        name='completar-pedido'),
    path('negocios/<int:pk>/productos/', ProductosPublicosView.as_view(), name='productos-publicos'),
    # Repartidor
    path('repartidor/perfil/',    PerfilRepartidorView.as_view(),    name='perfil-repartidor'),
    path('repartidor/register/',  RegisterRepartidorView.as_view(),  name='register-repartidor'),
]