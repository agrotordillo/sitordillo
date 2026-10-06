import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.utils.http import content_disposition_header

from apps.core.archivos import puede_descargar

# Solo estos tipos se muestran dentro del navegador; cualquier otro (HTML,
# SVG, ...) se fuerza a descarga para que un archivo subido nunca se
# ejecute como página de este sitio.
EXTENSIONES_EN_LINEA = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"})


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


def servir_archivo_protegido(request, ruta):
    """Entrega un archivo de MEDIA solo si el usuario puede ver el registro
    al que pertenece (ver apps.core.archivos). Responde 404 -no 403- cuando
    no puede, para no confirmar siquiera que el archivo existe.

    Con settings.MEDIA_X_ACCEL_REDIRECT (producción detrás de nginx) Django
    solo autoriza y nginx entrega el archivo desde una location `internal`;
    sin él, Django lo transmite con FileResponse."""
    if ".." in ruta.split("/") or "\\" in ruta or not puede_descargar(request.user, ruta):
        raise Http404

    nombre = os.path.basename(ruta)
    extension = os.path.splitext(nombre)[1].lower()
    tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"

    prefijo_accel = settings.MEDIA_X_ACCEL_REDIRECT
    if prefijo_accel:
        respuesta = HttpResponse(content_type=tipo)
        respuesta["X-Accel-Redirect"] = f"{prefijo_accel.rstrip('/')}/{quote(ruta)}"
    else:
        try:
            archivo = default_storage.open(ruta, "rb")
        except (FileNotFoundError, SuspiciousFileOperation):
            raise Http404
        respuesta = FileResponse(archivo, content_type=tipo)

    respuesta["Content-Disposition"] = content_disposition_header(
        as_attachment=extension not in EXTENSIONES_EN_LINEA, filename=nombre
    )
    respuesta["Cache-Control"] = "private, no-store"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta
