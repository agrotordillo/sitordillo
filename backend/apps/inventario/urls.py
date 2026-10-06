from django.urls import path

from .views.inventario_views import ExistenciaListView, LoteListView
from .views.correccion_views import corregir_lote_view, reportar_merma_view
from .views.surtimiento_views import SurtimientoListView
from .views.kardex_views import kardex_producto_view
from .views.estancado_views import existencia_sin_movimiento_view
from .views.movimiento_costo_views import MovimientoCostoListView
from .views.costeo_views import CosteoProductoListView
from .views.conversion_views import (
    ConversionListView,
    RecetaConversionCreateView,
    RecetaConversionListView,
    RecetaConversionUpdateView,
    crear_conversion_view,
)
from .views.ensamble_views import EnsamblePaqueteListView, crear_ensamble_view
from .views.movimiento_almacen_views import (
    MovimientoAlmacenCreateView,
    MovimientoAlmacenDetailView,
    MovimientoAlmacenListView,
    MovimientoAlmacenUpdateView,
    movimiento_almacen_aplicar_view,
    movimiento_almacen_cancelar_view,
)

app_name = "inventario"

urlpatterns = [
    path("lotes/", LoteListView.as_view(), name="lote-list"),
    path("lotes/<int:pk>/corregir/", corregir_lote_view, name="lote-corregir"),
    path("lotes/<int:pk>/merma/", reportar_merma_view, name="lote-merma"),
    path("existencias/", ExistenciaListView.as_view(), name="existencia-list"),
    path("surtimiento/", SurtimientoListView.as_view(), name="surtimiento-list"),
    path("kardex/", kardex_producto_view, name="kardex-producto"),
    path("existencia-sin-movimiento/", existencia_sin_movimiento_view, name="existencia-sin-movimiento"),
    path("movimientos-costo/", MovimientoCostoListView.as_view(), name="movimiento-costo-list"),
    path("costeo-producto/", CosteoProductoListView.as_view(), name="costeo-producto-list"),
    path("conversiones/", ConversionListView.as_view(), name="conversion-list"),
    path("conversiones/crear/", crear_conversion_view, name="conversion-create"),
    path("conversiones/recetas/", RecetaConversionListView.as_view(), name="receta-conversion-list"),
    path("conversiones/recetas/crear/", RecetaConversionCreateView.as_view(), name="receta-conversion-create"),
    path(
        "conversiones/recetas/<int:pk>/editar/",
        RecetaConversionUpdateView.as_view(),
        name="receta-conversion-update",
    ),
    path("ensambles/", EnsamblePaqueteListView.as_view(), name="ensamble-list"),
    path("ensambles/crear/", crear_ensamble_view, name="ensamble-create"),
    path("movimientos-almacen/", MovimientoAlmacenListView.as_view(), name="movimiento-almacen-list"),
    path("movimientos-almacen/crear/", MovimientoAlmacenCreateView.as_view(), name="movimiento-almacen-create"),
    path("movimientos-almacen/<int:pk>/", MovimientoAlmacenDetailView.as_view(), name="movimiento-almacen-detail"),
    path(
        "movimientos-almacen/<int:pk>/editar/",
        MovimientoAlmacenUpdateView.as_view(),
        name="movimiento-almacen-update",
    ),
    path(
        "movimientos-almacen/<int:pk>/aplicar/",
        movimiento_almacen_aplicar_view,
        name="movimiento-almacen-aplicar",
    ),
    path(
        "movimientos-almacen/<int:pk>/cancelar/",
        movimiento_almacen_cancelar_view,
        name="movimiento-almacen-cancelar",
    ),
]
