from django.urls import path

from .views.pedido_views import (
    PedidoCreateView,
    PedidoListView,
    PedidoUpdateView,
    cancelar_pedido_view,
)
from .views.conversion_views import buscar_pedido_view, convertir_pedido_view

app_name = "pedidos"

urlpatterns = [
    path("", PedidoListView.as_view(), name="pedido-list"),
    path("crear/", PedidoCreateView.as_view(), name="pedido-create"),
    path("<int:pk>/editar/", PedidoUpdateView.as_view(), name="pedido-update"),
    path("<int:pk>/cancelar/", cancelar_pedido_view, name="pedido-cancelar"),
    path("convertir/", buscar_pedido_view, name="pedido-buscar"),
    path("<int:pk>/convertir/", convertir_pedido_view, name="pedido-convertir"),
]
