from django.apps import AppConfig


def _gastos_visibles_con_permiso(user):
    """Mismo alcance que el listado y la edición de gastos (permiso
    estricto del módulo + sucursal, ver gastos.services.gastos_visibles)."""
    from .models import Gasto
    from .services import gastos_visibles

    return gastos_visibles(user) if user.has_perm("gastos.view_gasto") else Gasto.objects.none()


class GastosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gastos'
    verbose_name = 'Gastos'

    def ready(self):
        from apps.core.archivos import registrar_archivo_protegido

        registrar_archivo_protegido("gastos/comprobantes", "comprobante", _gastos_visibles_con_permiso)
