from django.conf import settings
from django.contrib.auth.views import redirect_to_login

EXEMPT_PATH_PREFIXES = ('/admin/', settings.STATIC_URL, settings.MEDIA_URL)
EXEMPT_PATHS = frozenset(filter(None, (
    settings.LOGIN_URL,
    '/logout/',
    getattr(settings, 'AXES_LOCKOUT_URL', None),
)))


class LoginRequiredMiddleware:
    """Requires an authenticated session for every view except login/logout/lockout, admin and static/media assets."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not self._is_exempt(request.path):
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        return self.get_response(request)

    @staticmethod
    def _is_exempt(path):
        return path.startswith(EXEMPT_PATH_PREFIXES) or path in EXEMPT_PATHS
