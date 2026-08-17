from django.urls import path

from .views.orden_compra_views import OrdenCompraCreateView, OrdenCompraListView

app_name = "compras"

urlpatterns = [
    path("", OrdenCompraListView.as_view(), name="orden-list"),
    path("crear/", OrdenCompraCreateView.as_view(), name="orden-create"),
]
