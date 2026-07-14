from rest_framework.permissions import BasePermission


class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol is not None and
            request.user.rol.nombre == 'admin'
        )


class EsCliente(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol is not None and
            request.user.rol.nombre == 'cliente'
        )


class EsRepartidor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol is not None and
            request.user.rol.nombre == 'repartidor'
        )


class EsPropietarioDeNegocio(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'negocio')
        )


class EsAdminORepartidor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.rol is not None and
            request.user.rol.nombre in ['admin', 'repartidor']
        )