from django.urls import path

from .views.inventario_views import ExistenciaListView, LoteListView

app_name = "inventario"

urlpatterns = [
    path("lotes/", LoteListView.as_view(), name="lote-list"),
    path("existencias/", ExistenciaListView.as_view(), name="existencia-list"),
]
