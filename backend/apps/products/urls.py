from django.urls import path

from .views.product_views import ProductCreateView, ProductListView, ProductToggleActivoView, ProductUpdateView
from .views.category_views import CategoryCreateView, CategoryListView, CategoryUpdateView
from .views.subcategory_views import SubcategoryCreateView, SubcategoryListView, SubcategoryUpdateView
from .views.brand_views import BrandCreateView, BrandListView
from .views.linea_views import LineaCreateView, LineaListView
from .views.clase_views import ClaseCreateView, ClaseListView
from .views.warehouse_views import WarehouseCreateView, WarehouseListView, WarehouseUpdateView
from .views.punto_venta_views import PuntoVentaCreateView, PuntoVentaListView, PuntoVentaUpdateView
from .views.turno_views import TurnoListView, abrir_turno_view, cerrar_turno_view
from .views.unit_measure_views import UnitMeasureCreateView, UnitMeasureListView
from .views.paquete_views import paquete_componentes_view
from .views.precio_views import producto_precios_view
from .views.stock_sucursal_views import producto_stock_sucursal_view
from .views.export_views import producto_exportar_excel_view

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="product-list"),
    path("exportar/", producto_exportar_excel_view, name="product-exportar"),
    path("crear/", ProductCreateView.as_view(), name="product-create"),
    path("<int:pk>/editar/", ProductUpdateView.as_view(), name="product-update"),
    path("<int:pk>/toggle-activo/", ProductToggleActivoView.as_view(), name="product-toggle-activo"),
    path("<int:pk>/paquete/", paquete_componentes_view, name="paquete-componentes"),
    path("<int:pk>/precios/", producto_precios_view, name="producto-precios"),
    path("<int:pk>/stock-sucursal/", producto_stock_sucursal_view, name="producto-stock-sucursal"),
    path("categorias/", CategoryListView.as_view(), name="category-list"),
    path("categorias/crear/", CategoryCreateView.as_view(), name="category-create"),
    path("categorias/<int:pk>/editar/", CategoryUpdateView.as_view(), name="category-update"),
    path("subcategorias/", SubcategoryListView.as_view(), name="subcategory-list"),
    path("subcategorias/crear/", SubcategoryCreateView.as_view(), name="subcategory-create"),
    path("subcategorias/<int:pk>/editar/", SubcategoryUpdateView.as_view(), name="subcategory-update"),
    path("marcas/", BrandListView.as_view(), name="brand-list"),
    path("marcas/crear/", BrandCreateView.as_view(), name="brand-create"),
    path("lineas/", LineaListView.as_view(), name="linea-list"),
    path("lineas/crear/", LineaCreateView.as_view(), name="linea-create"),
    path("clases/", ClaseListView.as_view(), name="clase-list"),
    path("clases/crear/", ClaseCreateView.as_view(), name="clase-create"),
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
    path("turnos/", TurnoListView.as_view(), name="turno-list"),
    path("turnos/abrir/", abrir_turno_view, name="turno-abrir"),
    path("turnos/<int:pk>/cerrar/", cerrar_turno_view, name="turno-cerrar"),
    path("unidades-medida/", UnitMeasureListView.as_view(), name="unit-list"),
    path("unidades-medida/crear/", UnitMeasureCreateView.as_view(), name="unit-create"),
]
