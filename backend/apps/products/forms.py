from apps.core.forms import BaseModelForm
from .models import Producto, Categoria, Subcategoria, Marca, Proveedor, UnidadMedida


class ProductForm(BaseModelForm):
    class Meta:
        model = Producto
        fields = [
            "nombre",
            "marca",
            "proveedor",
            "sku",
            "codigo_barras",
            "categoria",
            "subcategoria",
            "tipo",
            "unidad_medida",
            "descripcion",
            "notas",
            "precio_costo",
            "precio_venta",
            "stock_minimo",
            "stock_maximo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cat_id = self.data.get("categoria") if self.is_bound else None
        if not cat_id and self.instance.pk:
            cat_id = self.instance.categoria_id
        if cat_id:
            self.fields["subcategoria"].queryset = Subcategoria.objects.filter(
                categoria_id=cat_id, is_active=True
            )
        else:
            self.fields["subcategoria"].queryset = Subcategoria.objects.none()


class CategoryForm(BaseModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]


class SubcategoryForm(BaseModelForm):
    class Meta:
        model = Subcategoria
        fields = ["nombre", "categoria", "descripcion"]


class BrandForm(BaseModelForm):
    class Meta:
        model = Marca
        fields = ["nombre", "descripcion"]


class SupplierForm(BaseModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "descripcion"]


class UnitMeasureForm(BaseModelForm):
    class Meta:
        model = UnidadMedida
        fields = ["nombre", "abreviatura"]
