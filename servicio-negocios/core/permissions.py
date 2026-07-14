from rest_framework.permissions import BasePermission


def _tiene_rol(request, *roles):
    usuario = request.user
    return bool(usuario and getattr(usuario, "is_authenticated", False) and getattr(usuario, "rol", None) in roles)


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "admin")


class EsCliente(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "cliente")


class EsRepartidor(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "repartidor")


class EsAdminORepartidor(BasePermission):
    def has_permission(self, request, view):
        return _tiene_rol(request, "admin", "repartidor")
