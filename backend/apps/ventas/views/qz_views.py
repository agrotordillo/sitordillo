"""Certificado y firma para QZ Tray (ver ventas/ticket.py y venta_ticket.html).

Sin esto, cada conexión de QZ Tray es "anónima" y el checkbox "Remember
this decision" de su diálogo de confirmación no sirve de nada -no hay
ningún certificado estable contra el cual recordar la decisión-. Firmando
cada solicitud con la llave privada del servidor, QZ Tray puede verificar
la conexión contra el certificado (público) de qz_certificado_view y, una
vez que ese mismo certificado se instale como `override.crt` en QZ Tray de
cada PC de caja, deja de preguntar por completo.

La llave privada vive en backend/.env/qz/ (fuera del repo, ver
.gitignore), igual que el resto de los secretos del proyecto. El
certificado no es secreto -se manda tal cual a quien lo pida-, pero vive
en el mismo lugar por simplicidad de despliegue: ambos archivos se
generan una sola vez y se copian igual a cada servidor/PC que los
necesite, nunca se regeneran por separado.
"""

import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound

_QZ_DIR = settings.BASE_DIR / ".env" / "qz"
_CERT_PATH = _QZ_DIR / "qz-certificate.pem"
_PRIVATE_KEY_PATH = _QZ_DIR / "qz-private-key.pem"


@login_required
def qz_certificado_view(request):
    if not _CERT_PATH.exists():
        return HttpResponseNotFound("No está configurado el certificado de QZ Tray.")
    return HttpResponse(_CERT_PATH.read_text(), content_type="text/plain")


@login_required
def qz_firmar_view(request):
    mensaje = request.GET.get("request", "")
    if not mensaje:
        return HttpResponseBadRequest("Falta el parámetro 'request'.")
    if not _PRIVATE_KEY_PATH.exists():
        return HttpResponseNotFound("No está configurada la llave privada de QZ Tray.")

    llave_privada = serialization.load_pem_private_key(_PRIVATE_KEY_PATH.read_bytes(), password=None)
    firma = llave_privada.sign(mensaje.encode("utf-8"), padding.PKCS1v15(), hashes.SHA512())
    return HttpResponse(base64.b64encode(firma), content_type="text/plain")
