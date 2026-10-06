import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth
from urllib3.exceptions import NewConnectionError

# Respuestas de un intermediario (proxy/balanceador) que se cansó de esperar
# a Facturama: la solicitud sí le llegó y pudo haberse procesado.
ESTATUS_HTTP_INCIERTOS = frozenset({502, 504})


class FacturamaError(Exception):
    """`incierto=True` cuando la solicitud pudo haber llegado y procesarse
    en Facturama aunque aquí se haya recibido un error (se agotó el tiempo
    esperando la respuesta, se cortó la conexión a medio camino, la
    respuesta llegó ilegible...). Al timbrar, reintentar en ese caso puede
    emitir un CFDI duplicado: hay que verificar primero en Facturama."""

    def __init__(self, message, status_code=None, response_body=None, incierto=False):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.incierto = incierto


def _fallo_antes_de_enviar(exc):
    """True si la solicitud nunca llegó a Facturama (no se pudo ni abrir la
    conexión): reintentar es seguro. Cualquier otro fallo de red deja la
    duda de si Facturama alcanzó a procesarla."""
    if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.SSLError)):
        return True
    if isinstance(exc, requests.exceptions.ConnectionError):
        causa = exc.args[0] if exc.args else None
        return isinstance(getattr(causa, "reason", causa), NewConnectionError)
    return False


class FacturamaClient:
    """Cliente HTTP para la API REST de Facturama (CFDI 4.0).
    Documentación: https://apisandbox.facturama.mx/Docs
    """

    def __init__(self):
        self.base_url = settings.FACTURAMA_BASE_URL
        self.auth = HTTPBasicAuth(settings.FACTURAMA_API_USER, settings.FACTURAMA_API_PASSWORD)

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")
        try:
            # El timbrado real puede tardar mas de 30s; se da margen amplio.
            response = requests.request(method, url, auth=self.auth, headers=headers, timeout=90, **kwargs)
        except requests.RequestException as e:
            raise FacturamaError(
                f"Error de conexión con Facturama: {e}", incierto=not _fallo_antes_de_enviar(e)
            ) from e

        if response.status_code >= 400:
            raise FacturamaError(
                f"Facturama respondió {response.status_code}: {response.text[:800]}",
                status_code=response.status_code,
                response_body=response.text,
                incierto=response.status_code in ESTATUS_HTTP_INCIERTOS,
            )
        return response

    def buscar_productos_servicios(self, keyword):
        resp = self._request("GET", "/catalogs/ProductsOrServices", params={"keyword": keyword})
        return resp.json() if resp.content else []

    def buscar_unidades(self, keyword):
        resp = self._request("GET", "/catalogs/Units", params={"keyword": keyword})
        return resp.json() if resp.content else []

    def crear_cfdi(self, payload):
        resp = self._request("POST", "/3/cfdis", json=payload)
        # Una respuesta exitosa que no se puede leer, o que no trae el Id del
        # comprobante, no garantiza que no se haya timbrado: es incierta.
        try:
            data = resp.json()
        except ValueError as e:
            raise FacturamaError(
                "Facturama respondió sin error pero con una respuesta ilegible.",
                status_code=resp.status_code,
                response_body=resp.text,
                incierto=True,
            ) from e
        if not isinstance(data, dict) or not data.get("Id"):
            raise FacturamaError(
                "Facturama respondió sin el Id del comprobante.",
                status_code=resp.status_code,
                response_body=resp.text,
                incierto=True,
            )
        return data

    def obtener_pdf_base64(self, facturama_id, tipo="issued"):
        # La respuesta es JSON -{"ContentEncoding":"base64","ContentType":
        # "pdf","ContentLength":N,"Content":"<base64>"}-, no el base64 como
        # texto plano: hay que extraer "Content", no decodificar el JSON
        # completo (eso da "Incorrect padding" al hacer b64decode).
        resp = self._request("GET", f"/Cfdi/pdf/{tipo}/{facturama_id}")
        return resp.json()["Content"]

    def obtener_xml_base64(self, facturama_id, tipo="issued"):
        resp = self._request("GET", f"/Cfdi/xml/{tipo}/{facturama_id}")
        return resp.json()["Content"]

    def cancelar_cfdi(self, facturama_id, motivo="02", uuid_reemplazo=None, tipo="issued"):
        # NOTA: a diferencia de crear_cfdi (probado con éxito real), esta ruta
        # no se pudo confirmar con una cancelación exitosa en el sandbox (la
        # API respondió error 500 genérico "intentar más tarde" en las
        # pruebas). La ruta sí fue reconocida por el servidor (a diferencia de
        # otras variantes que dieron 404/405), así que es la más probable,
        # pero falta validarla en vivo cuando se necesite cancelar de verdad.
        params = {"type": tipo, "motive": motivo}
        if uuid_reemplazo:
            params["uuidReplacement"] = uuid_reemplazo
        resp = self._request("DELETE", f"/api/cfdi/{facturama_id}", params=params)
        return resp.json() if resp.content else {}
