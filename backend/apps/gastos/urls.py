from django.urls import path

from .views.bitacora_views import BitacoraAccesoListView
from .views.centro_costo_views import CentroCostoCreateView, CentroCostoListView, CentroCostoUpdateView
from .views.concepto_views import ConceptoGastoCreateView, ConceptoGastoListView, ConceptoGastoUpdateView
from .views.gasto_views import GastoCreateView, GastoListView, GastoUpdateView
from .views.reporte_views import ReportePuntoEquilibrioView
from .views.vehiculo_views import VehiculoCreateView, VehiculoListView, VehiculoUpdateView

app_name = "gastos"

urlpatterns = [
    path("", GastoListView.as_view(), name="gasto-list"),
    path("crear/", GastoCreateView.as_view(), name="gasto-create"),
    path("<int:pk>/editar/", GastoUpdateView.as_view(), name="gasto-update"),
    path("reporte/", ReportePuntoEquilibrioView.as_view(), name="reporte"),
    path("centros-de-costo/", CentroCostoListView.as_view(), name="centro-costo-list"),
    path("centros-de-costo/crear/", CentroCostoCreateView.as_view(), name="centro-costo-create"),
    path("centros-de-costo/<int:pk>/editar/", CentroCostoUpdateView.as_view(), name="centro-costo-update"),
    path("conceptos/", ConceptoGastoListView.as_view(), name="concepto-list"),
    path("conceptos/crear/", ConceptoGastoCreateView.as_view(), name="concepto-create"),
    path("conceptos/<int:pk>/editar/", ConceptoGastoUpdateView.as_view(), name="concepto-update"),
    path("vehiculos/", VehiculoListView.as_view(), name="vehiculo-list"),
    path("vehiculos/crear/", VehiculoCreateView.as_view(), name="vehiculo-create"),
    path("vehiculos/<int:pk>/editar/", VehiculoUpdateView.as_view(), name="vehiculo-update"),
    path("bitacora-de-acceso/", BitacoraAccesoListView.as_view(), name="bitacora-acceso-list"),
]
