# django imports
from django.urls import path
# local imports
from apps.products.views.category_views import CategoryCreateView
from apps.products.views.product_views import ProductCreateView

app_name = "products"

urlpatterns = [
    path("categorias/crear/", CategoryCreateView.as_view(), name="category-create"),
    path("productos/crear/", ProductCreateView.as_view(), name="product-create"),
]