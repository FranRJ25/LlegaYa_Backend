from django.conf import settings

REFRESH_COOKIE_NAME = 'refresh_token'
REFRESH_COOKIE_PATH = '/api/auth/token/refresh/'   # el browser solo envía la cookie a este path


def set_refresh_cookie(response, refresh_token):
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    is_prod = not settings.DEBUG
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=str(refresh_token),
        httponly=True,
        secure=is_prod,
        samesite='None' if is_prod else 'Lax',
        path=REFRESH_COOKIE_PATH,
        max_age=max_age,
    )


def delete_refresh_cookie(response):
    is_prod = not settings.DEBUG
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        samesite='None' if is_prod else 'Lax',
    )
