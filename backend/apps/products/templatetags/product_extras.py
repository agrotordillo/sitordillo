from django import template
from apps.products.models import Producto

register = template.Library()


@register.filter
def producto_label(value):
    """Dado un id de Producto (o valor vacío), regresa una etiqueta legible
    'FOLIO · Nombre'. Se usa para prellenar el buscador de producto cuando
    un formulario se vuelve a mostrar (por ejemplo tras un error)."""
    if not value:
        return ""
    try:
        producto = Producto.objects.get(pk=value)
    except (Producto.DoesNotExist, ValueError, TypeError):
        return ""
    return f"{producto.folio} · {producto.nombre}"
