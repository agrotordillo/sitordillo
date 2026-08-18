import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth


class FacturamaError(Exception):
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


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
            raise FacturamaError(f"Error de conexión con Facturama: {e}") from e

        if response.status_code >= 400:
            raise FacturamaError(
                f"Facturama respondió {response.status_code}: {response.text[:800]}",
                status_code=response.status_code,
                response_body=response.text,
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
        return resp.json()

    def obtener_pdf_base64(self, facturama_id, tipo="issued"):
        resp = self._request("GET", f"/Cfdi/pdf/{tipo}/{facturama_id}")
        return resp.text

    def obtener_xml_base64(self, facturama_id, tipo="issued"):
        resp = self._request("GET", f"/Cfdi/xml/{tipo}/{facturama_id}")
        return resp.text

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
