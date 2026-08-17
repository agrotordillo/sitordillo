from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.products.models import Producto
from apps.proveedores.models import Proveedor
from .models import OrdenCompra, OrdenCompraDetalle


class OrdenCompraForm(BaseModelForm):
    class Meta:
        model = OrdenCompra
        fields = ["proveedor", "fecha_orden", "fecha_entrega_estimada", "estatus", "observaciones"]
        widgets = {
            "fecha_orden": forms.DateInput(attrs={"type": "date"}),
            "fecha_entrega_estimada": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)


class OrdenCompraDetalleForm(BaseModelForm):
    class Meta:
        model = OrdenCompraDetalle
        fields = ["producto", "cantidad", "precio_unitario"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True)
        self.fields["cantidad"].widget.attrs.update({
            "class": (self.fields["cantidad"].widget.attrs.get("class", "") + " fs-cantidad").strip(),
            "step": "0.01",
            "min": "0.01",
        })
        self.fields["precio_unitario"].widget.attrs.update({
            "class": (self.fields["precio_unitario"].widget.attrs.get("class", "") + " fs-precio").strip(),
            "step": "0.01",
            "min": "0",
        })


OrdenCompraDetalleFormSet = inlineformset_factory(
    OrdenCompra,
    OrdenCompraDetalle,
    form=OrdenCompraDetalleForm,
    extra=1,
    can_delete=True,
)
