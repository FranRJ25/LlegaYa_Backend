from types import SimpleNamespace

from rest_framework import authentication, exceptions
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


class UsuarioJWT(SimpleNamespace):
    """Representacion ligera del usuario autenticado, construida a partir de los claims
    del JWT emitido por servicio-usuarios. No hay consulta a base de datos."""

    is_authenticated = True
    is_anonymous = False


class StatelessJWTAuthentication(authentication.BaseAuthentication):
    """Valida el JWT emitido por servicio-usuarios sin consultar una base de datos local.
    Todos los microservicios comparten la misma SIGNING_KEY (SECRET_KEY) para poder
    verificar la firma sin llamar a servicio-usuarios en cada request."""

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != b"bearer":
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed("Encabezado de autorizacion invalido.")

        raw_token = header[1].decode()
        try:
            token = AccessToken(raw_token)
        except TokenError as exc:
            raise exceptions.AuthenticationFailed(str(exc))

        usuario = UsuarioJWT(
            id=int(token["user_id"]),
            email=token.get("email", ""),
            nombre=token.get("nombre", ""),
            rol=token.get("rol", ""),
        )
        return (usuario, token)

    def authenticate_header(self, request):
        return "Bearer"
