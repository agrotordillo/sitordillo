from django.apps import AppConfig


def _pagos_visibles(user):
    from .models import Pago

    return Pago.objects.all() if user.has_perm("pagos.view_pago") else Pago.objects.none()


class PagosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pagos'
    verbose_name = 'Pagos a proveedores'

    def ready(self):
        from apps.core.archivos import registrar_archivo_protegido

        registrar_archivo_protegido("pagos/comprobantes", "comprobante", _pagos_visibles)
