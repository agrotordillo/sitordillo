from django.urls import path

from .views.products import (
    BrandQuickCreateView,
    ProductoBuscarView,
    SubcategoriesByCategoryView,
    UnitMeasureQuickCreateView,
)
from .views.compras import PromocionVigenteView

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
        "compras/promocion-vigente/",
        PromocionVigenteView.as_view(),
        name="promocion-vigente",
    ),
]
