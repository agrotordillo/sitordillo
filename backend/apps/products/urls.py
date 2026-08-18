from django.urls import path

from .views.product_views import ProductCreateView, ProductListView
from .views.category_views import CategoryCreateView, CategoryListView
from .views.subcategory_views import SubcategoryCreateView, SubcategoryListView
from .views.brand_views import BrandCreateView, BrandListView
from .views.warehouse_views import WarehouseCreateView, WarehouseListView
from .views.unit_measure_views import UnitMeasureCreateView, UnitMeasureListView
from .views.paquete_views import paquete_componentes_view

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="product-list"),
    path("crear/", ProductCreateView.as_view(), name="product-create"),
    path("<int:pk>/paquete/", paquete_componentes_view, name="paquete-componentes"),
    path("categorias/", CategoryListView.as_view(), name="category-list"),
    path("categorias/crear/", CategoryCreateView.as_view(), name="category-create"),
    path("subcategorias/", SubcategoryListView.as_view(), name="subcategory-list"),
    path("subcategorias/crear/", SubcategoryCreateView.as_view(), name="subcategory-create"),
    path("marcas/", BrandListView.as_view(), name="brand-list"),
    path("marcas/crear/", BrandCreateView.as_view(), name="brand-create"),
    path("almacenes/", WarehouseListView.as_view(), name="warehouse-list"),
    path("almacenes/crear/", WarehouseCreateView.as_view(), name="warehouse-create"),
    path("unidades-medida/", UnitMeasureListView.as_view(), name="unit-list"),
    path("unidades-medida/crear/", UnitMeasureCreateView.as_view(), name="unit-create"),
]
