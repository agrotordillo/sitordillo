from django.urls import path

from .views.products import (
    BrandQuickCreateView,
    SubcategoriesByCategoryView,
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
        "products/units/create/",
        UnitMeasureQuickCreateView.as_view(),
        name="unit-quick-create",
    ),
]
