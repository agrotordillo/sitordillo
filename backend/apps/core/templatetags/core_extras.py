import uuid

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def token_envio(context):
    """Campo oculto con el token de un solo uso del formulario (ver
    apps.core.envio_unico). Al volver a mostrar un formulario con errores
    conserva el token que ya traía, así un reintento corregido sigue siendo
    el mismo envío. El JS global (modules/ui/envio-unico.js) deshabilita
    el botón de enviar de cualquier formulario que lo contenga."""
    from apps.core.envio_unico import CAMPO_TOKEN, token_del_post

    request = context.get("request")
    token = token_del_post(request) if request is not None and request.method == "POST" else None
    return format_html('<input type="hidden" name="{}" value="{}">', CAMPO_TOKEN, token or uuid.uuid4())


@register.filter
def moneda(valor, decimales=2):
    """Formatea un número como moneda con coma de miles y punto decimal,
    sin importar el idioma/locale activo del sitio (es-mx usa coma como
    separador decimal por default, lo que hace ver "256648,69" en vez de
    "256,648.69"). Uso: {{ valor|moneda }}."""
    if valor in (None, ""):
        return ""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return valor
    return f"{numero:,.{int(decimales)}f}"
