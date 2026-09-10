from django.urls import path

from .views.catalogo_views import (
    ComisionLineaCreateView,
    ComisionLineaListView,
    ComisionLineaUpdateView,
    ComisionProductoCreateView,
    ComisionProductoListView,
    ComisionProductoUpdateView,
)
from .views.reporte_views import reporte_comisiones_view

app_name = "comisiones"

urlpatterns = [
    path("", reporte_comisiones_view, name="reporte"),
    path("por-linea/", ComisionLineaListView.as_view(), name="comision-linea-list"),
    path("por-linea/crear/", ComisionLineaCreateView.as_view(), name="comision-linea-create"),
    path("por-linea/<int:pk>/editar/", ComisionLineaUpdateView.as_view(), name="comision-linea-update"),
    path("por-producto/", ComisionProductoListView.as_view(), name="comision-producto-list"),
    path("por-producto/crear/", ComisionProductoCreateView.as_view(), name="comision-producto-create"),
    path("por-producto/<int:pk>/editar/", ComisionProductoUpdateView.as_view(), name="comision-producto-update"),
]
