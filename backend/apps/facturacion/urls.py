from django.urls import path

from .views.catalogo_sat_views import buscar_clave_prod_serv_view, buscar_clave_unidad_view
from .views.empresa_views import empresa_config_view
from .views.factura_views import (
    FacturaListView,
    cancelar_factura_view,
    generar_factura_view,
    timbrar_factura_view,
)

app_name = "facturacion"

urlpatterns = [
    path("catalogo-sat/producto-servicio/", buscar_clave_prod_serv_view, name="buscar-clave-prod-serv"),
    path("catalogo-sat/unidad/", buscar_clave_unidad_view, name="buscar-clave-unidad"),
    path("empresa/", empresa_config_view, name="empresa-config"),
    path("", FacturaListView.as_view(), name="factura-list"),
    path("ventas/<int:venta_pk>/generar/", generar_factura_view, name="factura-generar"),
    path("<int:pk>/timbrar/", timbrar_factura_view, name="factura-timbrar"),
    path("<int:pk>/cancelar/", cancelar_factura_view, name="factura-cancelar"),
]
