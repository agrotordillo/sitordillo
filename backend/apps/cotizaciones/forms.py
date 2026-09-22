from django import forms
from django.forms import inlineformset_factory

from django.core.exceptions import ValidationError

from apps.core.forms import BaseModelForm
from apps.core.scoping import almacen_principal, almacenes_visibles
from apps.clientes.models import Cliente
from apps.products.models import Almacen, Producto, PuntoVenta
from .models import Cotizacion, CotizacionDetalle


class CotizacionForm(BaseModelForm):
    class Meta:
        model = Cotizacion
        # fecha_cotizacion no se captura: toma el default del modelo
        # (timezone.now al momento de guardar). observaciones se oculta por
        # ahora (puede volver a exponerse más adelante si hace falta).
        fields = ["cliente", "almacen", "punto_venta"]
        widgets = {
            # Mismo patrón de búsqueda por texto que producto (ver
            # cliente-search.js): con el catálogo completo de clientes un
            # <select> deja de ser práctico.
            "cliente": forms.HiddenInput,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.filter(is_active=True)
        # Cotización nueva sin cliente explícito: precarga "Público en
        # general" (lo más común en mostrador); se puede cambiar buscando
        # otro cliente con el autocomplete.
        if not self.instance.pk and "cliente" not in self.initial:
            publico = Cliente.publico_general()
            if publico is not None:
                self.initial["cliente"] = publico.pk

        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                almacenes = almacenes.filter(pk__in=visibles.values("pk"))
        self.fields["almacen"].queryset = almacenes

        puntos_venta = PuntoVenta.objects.filter(is_active=True, almacen__in=almacenes).select_related("almacen")
        self.fields["punto_venta"].queryset = puntos_venta

        # Usuario con una sucursal fija (ver AsignacionSucursal.es_principal):
        # no tiene sentido que la elija cada vez, se fija sola y el campo se
        # oculta. Sin una sucursal principal clara (Administrador, o sin
        # asignación) sigue viendo el select normal.
        fijo = almacen_principal(user) if user is not None else None
        if fijo is not None:
            self.fields["almacen"].widget = forms.HiddenInput()
            if not self.instance.pk and "almacen" not in self.initial:
                self.initial["almacen"] = fijo.pk

            puntos_venta_fijo = puntos_venta.filter(almacen=fijo)
            self.fields["punto_venta"].queryset = puntos_venta_fijo
            # Con un único punto de venta en esa sucursal tampoco tiene
            # sentido elegirlo: se precarga y se oculta igual que almacén.
            if puntos_venta_fijo.count() == 1:
                self.fields["punto_venta"].widget = forms.HiddenInput()
                if not self.instance.pk and "punto_venta" not in self.initial:
                    self.initial["punto_venta"] = puntos_venta_fijo.first().pk

        # El número de cotización ya generado queda ligado al punto de venta
        # que lo produjo: una vez asignado, ni almacén ni punto de venta se
        # pueden volver a cambiar (dejarían el folio impreso sin relación
        # con la sucursal/caja real del registro).
        if self.instance.pk and self.instance.numero_documento:
            self.fields["almacen"].disabled = True
            self.fields["punto_venta"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        almacen = cleaned_data.get("almacen")
        punto_venta = cleaned_data.get("punto_venta")
        if almacen and punto_venta and punto_venta.almacen_id != almacen.pk:
            raise ValidationError({"punto_venta": "El punto de venta debe pertenecer a la sucursal seleccionada."})
        return cleaned_data


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
