from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.clientes.models import Cliente
from apps.products.models import Producto
from .models import Cotizacion, CotizacionDetalle


class CotizacionForm(BaseModelForm):
    class Meta:
        model = Cotizacion
        # fecha_cotizacion no se captura: toma el default del modelo
        # (timezone.now al momento de guardar). observaciones se oculta por
        # ahora (puede volver a exponerse más adelante si hace falta).
        # almacen/punto_venta/turno tampoco son campos del formulario: al
        # crear una cotización nueva se toman del turno propio y abierto de
        # quien la levanta (ver CotizacionCreateView), igual que en Ventas;
        # al editar una ya guardada simplemente no se tocan -quedan ligados
        # al folio que ya se generó con esos datos-.
        fields = ["cliente"]
        widgets = {
            # Mismo patrón de búsqueda por texto que producto (ver
            # cliente-search.js): con el catálogo completo de clientes un
            # <select> deja de ser práctico.
            "cliente": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        # Cotización nueva sin cliente explícito: precarga "Público en
        # general" (lo más común en mostrador); se puede cambiar buscando
        # otro cliente con el autocomplete.
        if not self.instance.pk and "cliente" not in self.initial:
            publico = Cliente.publico_general()
            if publico is not None:
                self.initial["cliente"] = publico.pk


class CotizacionDetalleForm(BaseModelForm):
    """descuento, lista_precio y estrategia_salida NO son campos del
    formulario a propósito: quien levanta una cotización tampoco manipula
    el precio (misma regla que en Ventas, ver VentaDetalleForm). La lista
    de precios (la del cliente si tiene una propia, si no "PUBLICO") y la
    estrategia de salida (siempre FIFO) las resuelve
    CotizacionCreateView/UpdateView.form_valid() al guardar, y
    precio_unitario -aunque sigue en el formulario, porque su valor real
    se pinta ahí- se sobreescribe ahí también, sin confiar en lo que haya
    llegado en el POST."""

    class Meta:
        model = CotizacionDetalle
        fields = ["producto", "cantidad", "precio_unitario"]
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
            "readonly": "readonly",
            "tabindex": "-1",
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
        self.fields["folio"].widget.attrs["placeholder"] = "Ej. 0101C0000001"
        self.fields["folio"].widget.attrs["autofocus"] = True
