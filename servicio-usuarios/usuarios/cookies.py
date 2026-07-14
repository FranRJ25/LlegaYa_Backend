from django.conf import settings

NOMBRE_COOKIE_REFRESH = "refresh_token"
RUTA_COOKIE_REFRESH = "/api/usuarios/token/refresh/"


def set_refresh_cookie(response, refresh_token: str):
    response.set_cookie(
        NOMBRE_COOKIE_REFRESH,
        str(refresh_token),
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path=RUTA_COOKIE_REFRESH,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    )


def delete_refresh_cookie(response):
    response.delete_cookie(NOMBRE_COOKIE_REFRESH, path=RUTA_COOKIE_REFRESH)
