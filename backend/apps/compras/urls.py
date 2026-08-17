from django.urls import path

from apps.inventario.views.recepcion_views import recepcion_compra_view
from .views.orden_compra_views import OrdenCompraCreateView, OrdenCompraListView

app_name = "compras"

urlpatterns = [
    path("", OrdenCompraListView.as_view(), name="orden-list"),
    path("crear/", OrdenCompraCreateView.as_view(), name="orden-create"),
    path("<int:pk>/recibir/", recepcion_compra_view, name="orden-recibir"),
]
