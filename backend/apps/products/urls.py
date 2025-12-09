# django imports
from django.urls import path
# local imports
from apps.products.views.product_views import (
    ProductCreateView,
    ProductListView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="product"),
    path("crear/", ProductCreateView.as_view(), name="product-create"),
]