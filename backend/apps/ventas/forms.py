from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.core.scoping import almacenes_visibles
from apps.clientes.models import Cliente
from apps.products.models import Almacen, Producto
from .models import DevolucionCliente, DevolucionClienteDetalle, Venta, VentaDetalle


class VentaForm(BaseModelForm):
    class Meta:
        model = Venta
        fields = ["cliente", "almacen", "forma_pago", "fecha_venta", "observaciones"]
        widgets = {
            "fecha_venta": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        # Un usuario restringido a una o varias sucursales (ver
        # AsignacionSucursal) solo puede registrar la venta en una de las
        # suyas; sin restricción (Administrador/Auxiliar administrador) ve
        # todas, igual que antes.
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                almacenes = almacenes.filter(pk__in=visibles.values("pk"))
        self.fields["almacen"].queryset = almacenes
        self.fields["fecha_venta"].input_formats = ["%Y-%m-%dT%H:%M"]


class VentaDetalleForm(BaseModelForm):
    class Meta:
        model = VentaDetalle
        fields = ["producto", "cantidad", "precio_unitario", "descuento", "estrategia_salida"]
        widgets = {
            # Con ~300 mil productos, un <select> normal es inviable: se
            # busca por texto (ver producto-search.js) y este campo solo
            # guarda el id elegido.
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


VentaDetalleFormSet = inlineformset_factory(
    Venta,
    VentaDetalle,
    form=VentaDetalleForm,
    extra=1,
    can_delete=True,
)


class DevolucionClienteForm(BaseModelForm):
    class Meta:
        model = DevolucionCliente
        fields = ["fecha", "motivo"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class DevolucionLineaForm(forms.Form):
    venta_detalle_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    reingresa_a_inventario = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "venta_detalle_id" or isinstance(field.widget, forms.CheckboxInput):
                continue
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()


DevolucionFormSet = forms.formset_factory(DevolucionLineaForm, extra=0)
