from django.urls import path

from .views.inventario_views import ExistenciaListView, LoteListView
from .views.correccion_views import corregir_lote_view, reportar_merma_view
from .views.surtimiento_views import SurtimientoListView
from .views.kardex_views import kardex_producto_view
from .views.estancado_views import existencia_sin_movimiento_view
from .views.movimiento_costo_views import MovimientoCostoListView
from .views.conversion_views import (
    ConversionListView,
    RecetaConversionCreateView,
    RecetaConversionListView,
    RecetaConversionUpdateView,
    crear_conversion_view,
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
    path("conversiones/", ConversionListView.as_view(), name="conversion-list"),
    path("conversiones/crear/", crear_conversion_view, name="conversion-create"),
    path("conversiones/recetas/", RecetaConversionListView.as_view(), name="receta-conversion-list"),
    path("conversiones/recetas/crear/", RecetaConversionCreateView.as_view(), name="receta-conversion-create"),
    path(
        "conversiones/recetas/<int:pk>/editar/",
        RecetaConversionUpdateView.as_view(),
        name="receta-conversion-update",
    ),
]
