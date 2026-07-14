from rest_framework.permissions import BasePermission


def _tiene_rol(request, nombre_rol):
    usuario = request.user
    return bool(usuario and usuario.is_authenticated and usuario.rol and usuario.rol.nombre == nombre_rol)


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "admin")


class EsCliente(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "cliente")


class EsRepartidor(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "repartidor")
