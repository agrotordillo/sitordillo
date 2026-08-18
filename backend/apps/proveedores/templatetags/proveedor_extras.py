from django import template
from apps.proveedores.models import Proveedor

register = template.Library()


@register.filter
def proveedor_label(value):
    """Dado un id de Proveedor (o valor vacío), regresa una etiqueta legible
    'RFC · Nombre'. Se usa para prellenar el buscador de proveedor cuando
    un formulario se vuelve a mostrar (por ejemplo tras un error)."""
    if not value:
        return ""
    try:
        proveedor = Proveedor.objects.get(pk=value)
    except (Proveedor.DoesNotExist, ValueError, TypeError):
        return ""
    return f"{proveedor.rfc} · {proveedor.display_name}"
