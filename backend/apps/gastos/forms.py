from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.products.models import Almacen
from apps.proveedores.models import Proveedor
from .models import CategoriaGasto, CentroCosto, Gasto, GastoDistribucion


class CentroCostoForm(BaseModelForm):
    class Meta:
        model = CentroCosto
        fields = ["nombre", "tipo", "almacen", "descripcion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        self.fields["almacen"].required = False
        self.fields["descripcion"].required = False


class CategoriaGastoForm(BaseModelForm):
    class Meta:
        model = CategoriaGasto
        fields = ["nombre", "naturaleza", "descripcion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descripcion"].required = False


class GastoForm(BaseModelForm):
    class Meta:
        model = Gasto
        fields = [
            "centro_costo", "categoria", "proveedor", "concepto", "fecha", "importe",
            "facturado", "referencia_factura", "comprobante", "es_compartido", "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["centro_costo"].queryset = CentroCosto.objects.filter(is_active=True)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["proveedor"].required = False
        self.fields["referencia_factura"].required = False
        self.fields["comprobante"].required = False
        self.fields["observaciones"].required = False


class GastoDistribucionForm(BaseModelForm):
    class Meta:
        model = GastoDistribucion
        fields = ["centro_costo", "monto"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["centro_costo"].queryset = CentroCosto.objects.filter(
            is_active=True, tipo=CentroCosto.Tipo.SUCURSAL
        )
        self.fields["monto"].widget.attrs.update({
            "class": (self.fields["monto"].widget.attrs.get("class", "") + " fs-monto").strip(),
            "step": "0.01",
            "min": "0.01",
        })


GastoDistribucionFormSet = inlineformset_factory(
    Gasto,
    GastoDistribucion,
    form=GastoDistribucionForm,
    extra=1,
    can_delete=True,
)
