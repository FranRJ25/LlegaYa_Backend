from django.conf import settings

REFRESH_COOKIE_NAME = 'refresh_token'
REFRESH_COOKIE_PATH = '/api/auth/token/refresh/'   # el browser solo envía la cookie a este path


def set_refresh_cookie(response, refresh_token):
    max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=str(refresh_token),
        httponly=True,
        secure=not settings.DEBUG,  # False en dev HTTP, True en prod HTTPS
        samesite='Lax',             # dev con proxy = mismo origen; prod cross-site: 'None' + secure=True
        path=REFRESH_COOKIE_PATH,
        max_age=max_age,
    )


def delete_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, samesite='Lax')
