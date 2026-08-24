from django import template

register = template.Library()


@register.filter
def get_item(diccionario, clave):
    """Permite hacer diccionario[clave] en el template usando una variable
    como clave (Django no soporta esa sintaxis de forma nativa). Se usa para
    reprellenar el monto capturado por cuenta en el formulario de pago
    múltiple cuando la página se vuelve a mostrar por un error."""
    if not diccionario:
        return None
    return diccionario.get(clave)
