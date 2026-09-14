from django.urls import path

from .views.catalogo_views import (
    ComisionColaboradorLineaCreateView,
    ComisionColaboradorLineaListView,
    ComisionColaboradorLineaUpdateView,
)
from .views.reporte_views import reporte_comisiones_ruta_view

app_name = "comisiones_ruta"

urlpatterns = [
    path("", reporte_comisiones_ruta_view, name="reporte"),
    path("por-colaborador/", ComisionColaboradorLineaListView.as_view(), name="comision-colaborador-linea-list"),
    path("por-colaborador/crear/", ComisionColaboradorLineaCreateView.as_view(), name="comision-colaborador-linea-create"),
    path("por-colaborador/<int:pk>/editar/", ComisionColaboradorLineaUpdateView.as_view(), name="comision-colaborador-linea-update"),
]
