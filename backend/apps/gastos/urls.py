from django.urls import path

from .views.categoria_views import CategoriaGastoCreateView, CategoriaGastoListView, CategoriaGastoUpdateView
from .views.centro_costo_views import CentroCostoCreateView, CentroCostoListView, CentroCostoUpdateView
from .views.gasto_views import GastoCreateView, GastoListView
from .views.reporte_views import ReportePuntoEquilibrioView

app_name = "gastos"

urlpatterns = [
    path("", GastoListView.as_view(), name="gasto-list"),
    path("crear/", GastoCreateView.as_view(), name="gasto-create"),
    path("reporte/", ReportePuntoEquilibrioView.as_view(), name="reporte"),
    path("centros-de-costo/", CentroCostoListView.as_view(), name="centro-costo-list"),
    path("centros-de-costo/crear/", CentroCostoCreateView.as_view(), name="centro-costo-create"),
    path("centros-de-costo/<int:pk>/editar/", CentroCostoUpdateView.as_view(), name="centro-costo-update"),
    path("categorias/", CategoriaGastoListView.as_view(), name="categoria-list"),
    path("categorias/crear/", CategoriaGastoCreateView.as_view(), name="categoria-create"),
    path("categorias/<int:pk>/editar/", CategoriaGastoUpdateView.as_view(), name="categoria-update"),
]
