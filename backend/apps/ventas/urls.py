from django.urls import path

from .views.venta_views import VentaCreateView, VentaListView, VentaTicketView
from .views.devolucion_views import DevolucionClienteListView, devolucion_cliente_view

app_name = "ventas"

urlpatterns = [
    path("", VentaListView.as_view(), name="venta-list"),
    path("crear/", VentaCreateView.as_view(), name="venta-create"),
    path("<int:pk>/ticket/", VentaTicketView.as_view(), name="venta-ticket"),
    path("<int:pk>/devolver/", devolucion_cliente_view, name="venta-devolver"),
    path("devoluciones/", DevolucionClienteListView.as_view(), name="devolucion-list"),
]
