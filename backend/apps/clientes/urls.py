from django.urls import path

from .views.cliente_views import ClienteCreateView, ClienteListView, ClienteUpdateView

app_name = "clientes"

urlpatterns = [
    path("", ClienteListView.as_view(), name="cliente-list"),
    path("crear/", ClienteCreateView.as_view(), name="cliente-create"),
    path("<int:pk>/editar/", ClienteUpdateView.as_view(), name="cliente-update"),
]
