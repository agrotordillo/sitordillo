import threading

from django.core.exceptions import PermissionDenied

from apps.core.views import permiso_denegado_view

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


class PermisoDenegadoMiddleware:
    """Convierte cualquier PermissionDenied -de
    @permission_required(..., raise_exception=True), de
    PermissionRequiredMixin, o de cualquier vista que la lance a mano- en
    la página 403 con el mismo diseño del resto del sistema
    (apps.core.views.permiso_denegado_view), en vez de la respuesta
    genérica de Django. Va después de LoginRequiredMiddleware en
    MIDDLEWARE (ver settings): a quien no está autenticado ese middleware
    ya lo mandó a la pantalla de login antes de llegar aquí, así que un
    403 real siempre es "sí eres alguien, pero no tienes este permiso"."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied):
            return permiso_denegado_view(request, exception)
        return None
