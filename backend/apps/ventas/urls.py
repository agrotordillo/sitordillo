from django.urls import path

from .views.venta_views import (
    VentaCreateView,
    VentaListView,
    VentaReportePDFView,
    VentaTicketView,
    recuperar_documento_view,
)
from .views.analisis_views import AnalisisVentasPrecioView, AnalisisVentasProductoView
from .views.devolucion_views import DevolucionClienteListView, devolucion_cliente_view
from .views.qz_views import qz_certificado_view, qz_firmar_view
from .views.retiro_views import RetiroEfectivoListView, RetiroEfectivoTicketView, retiro_efectivo_create_view

app_name = "ventas"

urlpatterns = [
    path("", VentaListView.as_view(), name="venta-list"),
    path("reporte.pdf", VentaReportePDFView.as_view(), name="venta-reporte-pdf"),
    path("crear/", VentaCreateView.as_view(), name="venta-create"),
    path("recuperar/", recuperar_documento_view, name="recuperar-documento"),
    path("<int:pk>/ticket/", VentaTicketView.as_view(), name="venta-ticket"),
    path("<int:pk>/devolver/", devolucion_cliente_view, name="venta-devolver"),
    path("devoluciones/", DevolucionClienteListView.as_view(), name="devolucion-list"),
    path("retiros/", RetiroEfectivoListView.as_view(), name="retiro-list"),
    path("retiros/crear/", retiro_efectivo_create_view, name="retiro-create"),
    path("retiros/<int:pk>/ticket/", RetiroEfectivoTicketView.as_view(), name="retiro-ticket"),
    path("analisis-por-producto/", AnalisisVentasProductoView.as_view(), name="analisis-producto"),
    path("analisis-por-precio/", AnalisisVentasPrecioView.as_view(), name="analisis-precio"),
    path("qz/certificado/",qz_certificado_view, name="qz-certificado"),
    path("qz/firmar/", qz_firmar_view, name="qz-firmar"),
]
