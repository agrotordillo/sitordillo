from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Submit, Row, Column
from django import forms
from apps.core.forms import BaseForm
from .models import Category, Product


class CategoryForm(BaseForm):
    """
    Formulario para la creación/edición de categorías de productos.
    """

    class Meta:
        model = Category
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "space-y-6"
        self.helper.label_class = "font-semibold text-gray-700"
        self.helper.layout = Layout(
            Row(Column(Field("name"), css_class="w-full")),
            Row(Column(Field("description"), css_class="w-full")),
            Submit("submit", "Guardar", css_class="btn btn-primary w-full"),
        )


class ProductForm(forms.ModelForm):
    """Formulario para creación y edición de productos."""

    class Meta:
        model = Product
        fields = [
            "sku",
            "barcode",
            "name",
            "product_type",
            # "category",
            "brand",
            "base_unit",
            "aux_unit",
            "aux_factor",
            "weight_kg",
            "purchase_price",
            "sale_price",
            "tax_rate",
            "global_stock",
            "min_stock",
            "is_stockable",
        ]
        widgets = {
            "product_type": forms.Select(attrs={"class": "w-full"}),
            "category": forms.Select(attrs={"class": "w-full"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "is_stockable": forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.attrs = {
            "class": "space-y-6",
            "novalidate": "novalidate",
        }
        self.helper.add_input(Submit("submit", "Guardar producto", css_class="btn-primary"))
