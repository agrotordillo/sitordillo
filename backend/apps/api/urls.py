from django.urls import path

from .views.products import (
    BrandQuickCreateView,
    SubcategoriesByCategoryView,
    SupplierQuickCreateView,
    UnitMeasureQuickCreateView,
)

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
        "products/suppliers/create/",
        SupplierQuickCreateView.as_view(),
        name="supplier-quick-create",
    ),
    path(
        "products/units/create/",
        UnitMeasureQuickCreateView.as_view(),
        name="unit-quick-create",
    ),
]
