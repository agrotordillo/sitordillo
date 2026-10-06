from django.apps import AppConfig


def _productos_visibles(user):
    from .models import Producto

    return Producto.objects.all() if user.has_perm("products.view_producto") else Producto.objects.none()


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.products'

    def ready(self):
        from apps.core.archivos import registrar_archivo_protegido

        registrar_archivo_protegido("productos", "imagen", _productos_visibles)
