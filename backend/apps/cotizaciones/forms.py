from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.clientes.models import Cliente
from apps.products.models import Almacen, Producto
from .models import Cotizacion, CotizacionDetalle


class CotizacionForm(BaseModelForm):
    class Meta:
        model = Cotizacion
        fields = ["cliente", "almacen", "fecha_cotizacion", "observaciones"]
        widgets = {
            "fecha_cotizacion": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        self.fields["fecha_cotizacion"].input_formats = ["%Y-%m-%dT%H:%M"]


class CotizacionDetalleForm(BaseModelForm):
    class Meta:
        model = CotizacionDetalle
        fields = ["producto", "cantidad", "precio_unitario", "descuento", "estrategia_salida"]
        widgets = {
            # Mismo patrón de búsqueda por texto que en Ventas (ver
            # producto-search.js): el <select> no es viable con ~300 mil
            # productos.
            "producto": forms.HiddenInput,
        }

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
        self.fields["descuento"].widget.attrs.update({
            "class": (self.fields["descuento"].widget.attrs.get("class", "") + " fs-descuento").strip(),
            "step": "0.01",
            "min": "0",
            "max": "100",
        })


CotizacionDetalleFormSet = inlineformset_factory(
    Cotizacion,
    CotizacionDetalle,
    form=CotizacionDetalleForm,
    extra=1,
    can_delete=True,
)


class BuscarFolioForm(forms.Form):
    folio = forms.CharField(label="Folio de cotización", max_length=32)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folio"].widget.attrs["class"] = "input"
        self.fields["folio"].widget.attrs["placeholder"] = "Ej. COT-XXXXXXXX"
        self.fields["folio"].widget.attrs["autofocus"] = True
