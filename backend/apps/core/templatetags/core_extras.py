from django import template

register = template.Library()


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
