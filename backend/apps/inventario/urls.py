from django.urls import path

from .views.inventario_views import ExistenciaListView, LoteListView
from .views.correccion_views import corregir_lote_view

app_name = "inventario"

urlpatterns = [
    path("lotes/", LoteListView.as_view(), name="lote-list"),
    path("lotes/<int:pk>/corregir/", corregir_lote_view, name="lote-corregir"),
    path("existencias/", ExistenciaListView.as_view(), name="existencia-list"),
]
