from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.clientes.models import Cliente
from apps.products.models import Producto
from .models import Pedido, PedidoDetalle


class PedidoForm(BaseModelForm):
    class Meta:
        model = Pedido
        # Mismo criterio que CotizacionForm: fecha_pedido toma el default
        # del modelo y almacen/punto_venta/turno se toman del turno propio y
        # abierto de quien lo levanta (ver PedidoCreateView). observaciones
        # sí se captura aquí -a diferencia de cotización-: en un pedido es
        # común anotar cuándo pasa el cliente por la mercancía.
        fields = ["cliente", "observaciones"]
        widgets = {
            "cliente": forms.HiddenInput,
            "observaciones": forms.TextInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        if not self.instance.pk and "cliente" not in self.initial:
            publico = Cliente.publico_general()
            if publico is not None:
                self.initial["cliente"] = publico.pk


class PedidoDetalleForm(BaseModelForm):
    """Igual que CotizacionDetalleForm: descuento, lista_precio y
    estrategia_salida no son campos del formulario, y precio_unitario se
    sobreescribe en la vista con fijar_precios_autorizados() sin confiar en
    lo que llegue en el POST."""

    class Meta:
        model = PedidoDetalle
        fields = ["producto", "cantidad", "precio_unitario"]
        widgets = {
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
            "readonly": "readonly",
            "tabindex": "-1",
        })


PedidoDetalleFormSet = inlineformset_factory(
    Pedido,
    PedidoDetalle,
    form=PedidoDetalleForm,
    extra=1,
    can_delete=True,
)


class BuscarFolioPedidoForm(forms.Form):
    folio = forms.CharField(label="Folio de pedido", max_length=32)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folio"].widget.attrs["class"] = "input"
        self.fields["folio"].widget.attrs["placeholder"] = "Ej. 0101P0000001"
        self.fields["folio"].widget.attrs["autofocus"] = True


class CancelarPedidoForm(forms.Form):
    motivo = forms.CharField(label="Motivo de cancelación", max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].widget.attrs["class"] = "input"
        self.fields["motivo"].widget.attrs["placeholder"] = "Ej. el cliente ya no pasó por la mercancía"
