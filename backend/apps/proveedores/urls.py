from django.urls import path

from .views.proveedor_views import SupplierCreateView, SupplierListView, SupplierUpdateView

app_name = "proveedores"

urlpatterns = [
    path("", SupplierListView.as_view(), name="supplier-list"),
    path("crear/", SupplierCreateView.as_view(), name="supplier-create"),
    path("<int:pk>/editar/", SupplierUpdateView.as_view(), name="supplier-update"),
]
