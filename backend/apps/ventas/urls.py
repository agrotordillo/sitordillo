from django.urls import path

from .views.venta_views import VentaCreateView, VentaListView, VentaTicketView, recuperar_documento_view
from .views.devolucion_views import DevolucionClienteListView, devolucion_cliente_view
from .views.qz_views import qz_certificado_view, qz_firmar_view

app_name = "ventas"

urlpatterns = [
    path("", VentaListView.as_view(), name="venta-list"),
    path("crear/", VentaCreateView.as_view(), name="venta-create"),
    path("recuperar/", recuperar_documento_view, name="recuperar-documento"),
    path("<int:pk>/ticket/", VentaTicketView.as_view(), name="venta-ticket"),
    path("<int:pk>/devolver/", devolucion_cliente_view, name="venta-devolver"),
    path("devoluciones/", DevolucionClienteListView.as_view(), name="devolucion-list"),
    path("qz/certificado/", qz_certificado_view, name="qz-certificado"),
    path("qz/firmar/", qz_firmar_view, name="qz-firmar"),
]
