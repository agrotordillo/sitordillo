from django.urls import path

from .views.product_views import ProductCreateView, ProductListView, ProductUpdateView
from .views.category_views import CategoryCreateView, CategoryListView, CategoryUpdateView
from .views.subcategory_views import SubcategoryCreateView, SubcategoryListView, SubcategoryUpdateView
from .views.brand_views import BrandCreateView, BrandListView
from .views.warehouse_views import WarehouseCreateView, WarehouseListView, WarehouseUpdateView
from .views.punto_venta_views import PuntoVentaCreateView, PuntoVentaListView, PuntoVentaUpdateView
from .views.unit_measure_views import UnitMeasureCreateView, UnitMeasureListView
from .views.paquete_views import paquete_componentes_view
from .views.precio_views import producto_precios_view

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="product-list"),
    path("crear/", ProductCreateView.as_view(), name="product-create"),
    path("<int:pk>/editar/", ProductUpdateView.as_view(), name="product-update"),
    path("<int:pk>/paquete/", paquete_componentes_view, name="paquete-componentes"),
    path("<int:pk>/precios/", producto_precios_view, name="producto-precios"),
    path("categorias/", CategoryListView.as_view(), name="category-list"),
    path("categorias/crear/", CategoryCreateView.as_view(), name="category-create"),
    path("categorias/<int:pk>/editar/", CategoryUpdateView.as_view(), name="category-update"),
    path("subcategorias/", SubcategoryListView.as_view(), name="subcategory-list"),
    path("subcategorias/crear/", SubcategoryCreateView.as_view(), name="subcategory-create"),
    path("subcategorias/<int:pk>/editar/", SubcategoryUpdateView.as_view(), name="subcategory-update"),
    path("marcas/", BrandListView.as_view(), name="brand-list"),
    path("marcas/crear/", BrandCreateView.as_view(), name="brand-create"),
    path("almacenes/", WarehouseListView.as_view(), name="warehouse-list"),
    path("almacenes/crear/", WarehouseCreateView.as_view(), name="warehouse-create"),
    path("almacenes/<int:pk>/editar/", WarehouseUpdateView.as_view(), name="warehouse-update"),
    path("almacenes/<int:almacen_id>/puntos-venta/", PuntoVentaListView.as_view(), name="punto-venta-list"),
    path(
        "almacenes/<int:almacen_id>/puntos-venta/crear/",
        PuntoVentaCreateView.as_view(),
        name="punto-venta-create",
    ),
    path("puntos-venta/<int:pk>/editar/", PuntoVentaUpdateView.as_view(), name="punto-venta-update"),
    path("unidades-medida/", UnitMeasureListView.as_view(), name="unit-list"),
    path("unidades-medida/crear/", UnitMeasureCreateView.as_view(), name="unit-create"),
]
