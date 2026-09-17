from django.shortcuts import render


def permiso_denegado_view(request, exception=None):
    """Página 403 con el mismo diseño que el resto del sistema (ver
    templates/403.html, que extiende _base.html). La usan tanto
    PermisoDenegadoMiddleware (la vía normal) como handler403 en
    config/urls.py (respaldo, por si algún PermissionDenied no pasara por
    el middleware). A diferencia del permission_denied() por default de
    Django, aquí sí se pasan los datos de contacto de la empresa (ver
    Empresa, apps.facturacion) para que el mensaje sea accionable -a quién
    contactar-, no solo informativo. Import diferido para no crear una
    dependencia de apps.core hacia apps.facturacion al cargar el módulo
    (mismo patrón que apps.core.scoping)."""
    from apps.facturacion.models import Empresa

    return render(request, "403.html", {"empresa": Empresa.objects.first()}, status=403)
