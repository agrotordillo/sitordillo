from django.apps import AppConfig


def _cobros_visibles(user):
    from .models import Cobro

    return Cobro.objects.all() if user.has_perm("cobros.view_cobro") else Cobro.objects.none()


class CobrosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cobros'
    verbose_name = 'Cuentas por cobrar'

    def ready(self):
        from apps.core.archivos import registrar_archivo_protegido

        registrar_archivo_protegido("cobros/comprobantes", "comprobante", _cobros_visibles)
