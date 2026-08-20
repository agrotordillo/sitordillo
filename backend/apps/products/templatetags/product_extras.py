from django import template
from apps.fiscal.models import ClaveProdServSAT, ClaveUnidadSAT
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


@register.filter
def clave_prod_serv_label(value):
    """Igual que producto_label, para la clave de producto/servicio SAT."""
    if not value:
        return ""
    try:
        clave = ClaveProdServSAT.objects.get(pk=value)
    except (ClaveProdServSAT.DoesNotExist, ValueError, TypeError):
        return ""
    return f"{clave.clave} · {clave.descripcion}"


@register.filter
def clave_unidad_label(value):
    """Igual que producto_label, para la clave de unidad SAT."""
    if not value:
        return ""
    try:
        clave = ClaveUnidadSAT.objects.get(pk=value)
    except (ClaveUnidadSAT.DoesNotExist, ValueError, TypeError):
        return ""
    return f"{clave.clave} · {clave.nombre}"
