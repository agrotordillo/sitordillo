from django.urls import path

from apps.inventario.views.recepcion_views import recepcion_compra_view
from .views.orden_compra_views import (
    OrdenCompraCreateView,
    OrdenCompraListView,
    OrdenCompraUpdateView,
    cargar_cfdi_view,
)
from .views.promocion_views import PromocionProveedorCreateView, PromocionProveedorListView

app_name = "compras"

urlpatterns = [
    path("", OrdenCompraListView.as_view(), name="orden-list"),
    path("crear/", OrdenCompraCreateView.as_view(), name="orden-create"),
    path("cargar-cfdi/", cargar_cfdi_view, name="orden-cargar-cfdi"),
    path("<int:pk>/editar/", OrdenCompraUpdateView.as_view(), name="orden-update"),
    path("<int:pk>/recibir/", recepcion_compra_view, name="orden-recibir"),
    path("promociones/", PromocionProveedorListView.as_view(), name="promocion-list"),
    path("promociones/crear/", PromocionProveedorCreateView.as_view(), name="promocion-create"),
]
