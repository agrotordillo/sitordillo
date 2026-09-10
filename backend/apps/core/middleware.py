import threading

_hilo_local = threading.local()


def get_current_user():
    """Usuario autenticado de la request en curso, o None si no hay
    ninguna request en este momento (un management command, una
    migración, o una tarea en segundo plano). Lo guarda
    CurrentUserMiddleware; lo consume BaseAbstractModel.save() para
    llenar created_by/updated_by sin que cada vista tenga que hacerlo a
    mano."""
    return getattr(_hilo_local, "user", None)


class CurrentUserMiddleware:
    """Guarda el usuario autenticado de la request en curso en una
    variable de hilo (thread-local), para que BaseAbstractModel.save()
    pueda llenar created_by/updated_by automáticamente -antes de este
    middleware, esos dos campos existían en el modelo pero nunca los
    llenaba nadie, así que ningún registro del sistema tenía guardado
    quién lo creó-.

    Se limpia siempre al terminar la request (en el finally), incluso si
    la vista truena, para no dejar el usuario de una request vieja
    "filtrándose" a lo que corra después en el mismo hilo (un worker de
    gunicorn reutiliza hilos entre requests)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        _hilo_local.user = usuario if (usuario is not None and usuario.is_authenticated) else None
        try:
            return self.get_response(request)
        finally:
            _hilo_local.user = None
