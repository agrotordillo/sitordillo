# django imports
from apps.core.forms import BaseModelForm
from django import forms
# local imports
from .models import Productos

class ProductForm(forms.ModelForm):
    """Formulario para creación y edición de productos."""
    class Meta:
        model = Productos
        fields = "__all__"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)






        # [
            # "sku",
            # "barcode",
            # "name",
            # "product_type",
            # # "category",
            # "brand",
            # "base_unit",
            # "aux_unit",
            # "aux_factor",
            # "weight_kg",
            # "purchase_price",
            # "sale_price",
            # "tax_rate",
            # "global_stock",
            # "min_stock",
            # "is_stockable",
        # ]


    #     widgets = {
    #         "product_type": forms.Select(attrs={"class": "w-full"}),
    #         "category": forms.Select(attrs={"class": "w-full"}),
    #         "description": forms.Textarea(attrs={"rows": 3}),
    #         "is_stockable": forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
    #     }

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.helper = FormHelper()
    #     self.helper.form_method = "post"
    #     self.helper.attrs = {
    #         "class": "space-y-6",
    #         "novalidate": "novalidate",
    #     }
    #     self.helper.add_input(Submit("submit", "Guardar producto", css_class="btn-primary"))
