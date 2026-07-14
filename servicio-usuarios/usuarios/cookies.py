from django.conf import settings

NOMBRE_COOKIE_REFRESH = "refresh_token"
RUTA_COOKIE_REFRESH = "/api/usuarios/token/refresh/"


def set_refresh_cookie(response, refresh_token: str):
    cross_site = getattr(settings, "COOKIE_CROSS_SITE", False)
    response.set_cookie(
        NOMBRE_COOKIE_REFRESH,
        str(refresh_token),
        httponly=True,
        secure=True if cross_site else not settings.DEBUG,
        samesite="None" if cross_site else "Lax",
        path=RUTA_COOKIE_REFRESH,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
    )


def delete_refresh_cookie(response):
    response.delete_cookie(NOMBRE_COOKIE_REFRESH, path=RUTA_COOKIE_REFRESH)
