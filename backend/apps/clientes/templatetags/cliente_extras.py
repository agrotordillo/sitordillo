from django import template
from apps.clientes.models import Cliente

register = template.Library()


@register.filter
def cliente_label(value):
    """Dado un id de Cliente (o valor vacío), regresa una etiqueta legible
    para prellenar el buscador de cliente cuando un formulario se vuelve a
    mostrar (por ejemplo tras un error)."""
    if not value:
        return ""
    try:
        cliente = Cliente.objects.get(pk=value)
    except (Cliente.DoesNotExist, ValueError, TypeError):
        return ""
    return f"{cliente.rfc} · {cliente.display_name}" if cliente.rfc else cliente.display_name
