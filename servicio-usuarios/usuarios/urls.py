from django.urls import path

from .views import (
    CookieTokenRefreshView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PerfilView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="usuarios-register"),
    path("login/", LoginView.as_view(), name="usuarios-login"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="usuarios-token-refresh"),
    path("logout/", LogoutView.as_view(), name="usuarios-logout"),
    path("perfil/", PerfilView.as_view(), name="usuarios-perfil"),
    path("password-reset-request/", PasswordResetRequestView.as_view(), name="usuarios-password-reset-request"),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view(), name="usuarios-password-reset-confirm"),
]
