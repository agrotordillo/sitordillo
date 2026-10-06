from rest_framework.permissions import BasePermission

from apps.products.permisos import puede_editar_productos


class RequierePermisos(BasePermission):
    """Exige, además de la sesión, los permisos de Django que la vista
    declare en `permisos_requeridos` -el mismo esquema que
    PermissionRequiredMixin en las vistas normales-. Un endpoint que
    modifica datos nunca debe quedarse solo con el IsAuthenticated por
    default del proyecto (B08 en docs/AUDITORIA.md)."""

    message = "No tienes permiso para realizar esta acción."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perms(view.permisos_requeridos)


class PuedeEditarProductos(BasePermission):
    """Para las altas rápidas de catálogos desde el formulario de producto
    (ver apps.products.permisos.puede_editar_productos)."""

    message = "Solo quien puede crear o editar productos puede dar de alta este catálogo."

    def has_permission(self, request, view):
        return puede_editar_productos(request.user)
