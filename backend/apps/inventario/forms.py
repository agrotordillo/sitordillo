from decimal import Decimal

from django import forms
from django.forms import formset_factory

from apps.products.models import Almacen, Producto


class RecepcionLineaForm(forms.Form):
    detalle_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad_recibir = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    numero_lote = forms.CharField(max_length=50, required=False)
    fecha_caducidad = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    costo_unitario = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    almacen = forms.ModelChoiceField(queryset=Almacen.objects.filter(is_active=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
        self.fields["detalle_id"].widget.attrs["class"] = ""


RecepcionFormSet = formset_factory(RecepcionLineaForm, extra=0)


class CorregirLoteForm(forms.Form):
    """Corrige un lote recibido con el producto equivocado, para el caso en
    que nada de ese lote se haya vendido/movido todavía (ver
    apps.inventario.services.corregir_recepcion)."""

    cantidad = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(is_active=True).exclude(tipo=Producto.TipoProducto.PAQUETE),
        widget=forms.HiddenInput,
    )
    motivo = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, lote=None, **kwargs):
        self.lote = lote
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
        if lote is not None and not self.is_bound:
            self.fields["cantidad"].initial = lote.cantidad_disponible

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if self.lote and cantidad > self.lote.cantidad_disponible:
            raise forms.ValidationError(
                f"No puedes corregir más de lo disponible en el lote ({self.lote.cantidad_disponible})."
            )
        return cantidad

    def clean_producto(self):
        producto = self.cleaned_data["producto"]
        if self.lote and producto.pk == self.lote.producto_id:
            raise forms.ValidationError("Elige un producto distinto al que ya tiene el lote.")
        return producto
