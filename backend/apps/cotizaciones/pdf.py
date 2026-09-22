"""Genera el PDF formal de una `Cotizacion` para entregar al cliente que la
solicitó. Solo tiene sentido mientras la cotización sigue abierta: en cuanto
se convierte a venta, la vista que sirve este PDF deja de ofrecerlo (ver
`CotizacionPDFView`).

Se usa xhtml2pdf (renderiza un template HTML/CSS de Django) en vez de
WeasyPrint para no depender de las librerías de sistema de GTK3, que en
Windows requieren instalación aparte del `pip install`.
"""

from io import BytesIO

from django.contrib.staticfiles.finders import find as encontrar_estatico
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def generar_pdf_cotizacion(cotizacion, empresa=None):
    html = render_to_string(
        "cotizaciones/cotizacion_pdf.html",
        {
            "cotizacion": cotizacion,
            "empresa": empresa,
            # xhtml2pdf no resuelve "{% static %}" (no tiene un request ni
            # sirve archivos por URL): se le da la ruta absoluta en disco,
            # igual que ya hace apps.pagos.services con el logo del correo.
            "logo_path": encontrar_estatico("src/logo.png"),
        },
    )
    buffer = BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer)
    if resultado.err:
        raise ValueError("No fue posible generar el PDF de la cotización.")
    return buffer.getvalue()
