from django.core.exceptions import ValidationError

# Lo que un servicio de negocio puede lanzar para avisar que la operación
# no procede: ValueError para sus reglas propias y ValidationError cuando
# viene de un full_clean() de modelo. Las vistas atrapan esta tupla completa
# -no solo ValueError- para mostrarle el motivo al usuario en vez de un 500.
ERRORES_DE_NEGOCIO = (ValueError, ValidationError)


def mensajes_de_error(exc):
    """Lista de mensajes legibles de una excepción de ERRORES_DE_NEGOCIO."""
    if isinstance(exc, ValidationError):
        return exc.messages
    return [str(exc)]


def errores_al_formulario(form, error):
    """Pasa un ValidationError de un full_clean() de modelo al formulario:
    cada mensaje a su campo si el formulario lo tiene, si no como error
    general."""
    if not hasattr(error, "error_dict"):
        for mensaje in error.messages:
            form.add_error(None, mensaje)
        return
    for campo, mensajes in error.message_dict.items():
        for mensaje in mensajes:
            form.add_error(campo if campo in form.fields else None, mensaje)
