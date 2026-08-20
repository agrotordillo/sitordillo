from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.forms import BaseModelForm
from .models import (
    Producto, Categoria, Subcategoria, Marca, Almacen, PaqueteComponente,
    UnidadMedida, ProductoPrecio,
)


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
            "clave_prod_serv_sat",
            "clave_unidad_sat",
            "almacen",
            "tipo_iva",
            "tasa_iva",
            "aplica_ieps",
            "tasa_ieps",
            "descripcion",
            "notas",
            "precio_costo",
            "precio_venta",
            "stock_minimo",
            "stock_maximo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
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


class WarehouseForm(BaseModelForm):
    class Meta:
        model = Almacen
        fields = ["nombre", "tipo"]


class UnitMeasureForm(BaseModelForm):
    class Meta:
        model = UnidadMedida
        fields = ["nombre", "abreviatura"]


class PaqueteComponenteForm(BaseModelForm):
    class Meta:
        model = PaqueteComponente
        fields = ["producto_componente", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto_componente"].queryset = Producto.objects.filter(
            is_active=True
        ).exclude(tipo=Producto.TipoProducto.PAQUETE)
        self.fields["cantidad"].widget.attrs.update({
            "class": (self.fields["cantidad"].widget.attrs.get("class", "") + " fs-cantidad").strip(),
            "step": "0.01",
            "min": "0.01",
        })


PaqueteComponenteFormSet = inlineformset_factory(
    Producto,
    PaqueteComponente,
    form=PaqueteComponenteForm,
    fk_name="paquete",
    extra=1,
    can_delete=True,
)


class ProductoPrecioForm(BaseModelForm):
    class Meta:
        model = ProductoPrecio
        fields = ["lista_precio", "almacen", "utilidad_pct", "precio_con_impuesto"]


class ProductoPrecioBaseFormSet(BaseInlineFormSet):
    """El UniqueConstraint de ProductoPrecio (producto, lista_precio, almacen)
    tiene `condition`, y Django no valida constraints condicionales a nivel
    de formulario (solo a nivel de base de datos) — sin este clean(), un
    duplicado pasaría is_valid() y tronaría hasta el .save() con un
    IntegrityError crudo."""

    def clean(self):
        super().clean()
        vistos = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            lista = form.cleaned_data.get("lista_precio")
            if lista is None:
                continue
            almacen = form.cleaned_data.get("almacen")
            key = (lista.id, almacen.id if almacen else None)
            if key in vistos:
                sucursal = f" en {almacen.nombre}" if almacen else " (general)"
                form.add_error("lista_precio", f"Ya hay otro precio de {lista.nombre}{sucursal} en esta lista.")
            vistos.add(key)


ProductoPrecioFormSet = inlineformset_factory(
    Producto,
    ProductoPrecio,
    form=ProductoPrecioForm,
    formset=ProductoPrecioBaseFormSet,
    fk_name="producto",
    extra=1,
    can_delete=True,
)
