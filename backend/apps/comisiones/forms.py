from django import forms

from apps.core.forms import BaseModelForm
from apps.products.models import Linea, Producto
from .models import ComisionLinea, ComisionProducto


class ComisionLineaForm(BaseModelForm):
    class Meta:
        model = ComisionLinea
        fields = ["linea", "porcentaje", "observaciones"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["linea"].queryset = Linea.objects.filter(is_active=True)


class ComisionProductoForm(BaseModelForm):
    class Meta:
        model = ComisionProducto
        fields = ["producto", "porcentaje", "observaciones"]
        widgets = {
            # Con miles de productos, un <select> normal es inviable: se
            # busca por folio/SKU/código/nombre (ver producto-search.js).
            "producto": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
