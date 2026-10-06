from django.urls import path

from .views.catalogo_sat_views import buscar_clave_prod_serv_view, buscar_clave_unidad_view
from .views.empresa_views import empresa_config_view
from .views.factura_views import (
    FacturaGlobalListView,
    FacturaListView,
    cancelar_factura_view,
    factura_global_detalle_view,
    factura_global_pdf_view,
    factura_global_xml_view,
    factura_pdf_view,
    factura_xml_view,
    generar_factura_global_view,
    generar_factura_view,
    liberar_timbrado_factura_view,
    liberar_timbrado_global_view,
    reintentar_timbrado_global_view,
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
    path("<int:pk>/liberar-timbrado/", liberar_timbrado_factura_view, name="factura-liberar-timbrado"),
    path("<int:pk>/cancelar/", cancelar_factura_view, name="factura-cancelar"),
    path("<int:pk>/pdf/", factura_pdf_view, name="factura-pdf"),
    path("<int:pk>/xml/", factura_xml_view, name="factura-xml"),
    path("globales/", FacturaGlobalListView.as_view(), name="factura-global-list"),
    path("globales/turnos/<int:turno_pk>/generar/", generar_factura_global_view, name="factura-global-generar"),
    path("globales/<int:pk>/", factura_global_detalle_view, name="factura-global-detalle"),
    path("globales/<int:pk>/timbrar/", reintentar_timbrado_global_view, name="factura-global-timbrar"),
    path(
        "globales/<int:pk>/liberar-timbrado/",
        liberar_timbrado_global_view,
        name="factura-global-liberar-timbrado",
    ),
    path("globales/<int:pk>/pdf/", factura_global_pdf_view, name="factura-global-pdf"),
    path("globales/<int:pk>/xml/", factura_global_xml_view, name="factura-global-xml"),
]
