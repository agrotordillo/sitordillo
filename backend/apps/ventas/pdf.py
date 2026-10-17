"""PDF del listado de ventas de un día, filtrado por forma de cobro (ver
VentaReportePDFView). Mismo motor que el PDF de cotización (xhtml2pdf),
para no depender de librerías de sistema."""

from io import BytesIO

from django.contrib.staticfiles.finders import find as encontrar_estatico
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def generar_pdf_reporte_ventas(contexto):
    html = render_to_string(
        "ventas/reporte_ventas_pdf.html",
        {**contexto, "logo_path": encontrar_estatico("src/logo.png")},
    )
    buffer = BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer)
    if resultado.err:
        raise ValueError("No fue posible generar el PDF del reporte de ventas.")
    return buffer.getvalue()
