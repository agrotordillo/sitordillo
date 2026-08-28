from django.urls import path

from .views.products import (
    BrandQuickCreateView,
    ProductoActualizarCostoView,
    ProductoBuscarView,
    ProductoResolverSkusView,
    SubcategoriesByCategoryView,
    UnitMeasureQuickCreateView,
)
from .views.compras import PromocionVigenteView
from .views.proveedores import ProveedorBuscarView
from .views.fiscal import ClaveProdServBuscarView, ClaveUnidadBuscarView

app_name = "api"

urlpatterns = [
    path(
        "products/subcategories/",
        SubcategoriesByCategoryView.as_view(),
        name="subcategories-by-category",
    ),
    path(
        "products/brands/create/",
        BrandQuickCreateView.as_view(),
        name="brand-quick-create",
    ),
    path(
        "products/units/create/",
        UnitMeasureQuickCreateView.as_view(),
        name="unit-quick-create",
    ),
    path(
        "products/buscar/",
        ProductoBuscarView.as_view(),
        name="producto-buscar",
    ),
    path(
        "products/actualizar-costo/",
        ProductoActualizarCostoView.as_view(),
        name="producto-actualizar-costo",
    ),
    path(
        "products/resolver-skus/",
        ProductoResolverSkusView.as_view(),
        name="producto-resolver-skus",
    ),
    path(
        "compras/promocion-vigente/",
        PromocionVigenteView.as_view(),
        name="promocion-vigente",
    ),
    path(
        "proveedores/buscar/",
        ProveedorBuscarView.as_view(),
        name="proveedor-buscar",
    ),
    path(
        "fiscal/claves-prod-serv/buscar/",
        ClaveProdServBuscarView.as_view(),
        name="clave-prod-serv-buscar",
    ),
    path(
        "fiscal/claves-unidad/buscar/",
        ClaveUnidadBuscarView.as_view(),
        name="clave-unidad-buscar",
    ),
]
