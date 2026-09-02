from decimal import Decimal

from django import forms
from django.forms import formset_factory

from apps.core.forms import BaseModelForm
from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen, Producto
from .models import RecetaConversion


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


class ReportarMermaForm(forms.Form):
    """Da de baja mercancía de un lote recibido que llegó en mal estado (ver
    apps.inventario.services.registrar_merma_recepcion)."""

    cantidad = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    motivo = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, lote=None, **kwargs):
        self.lote = lote
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if self.lote and cantidad > self.lote.cantidad_disponible:
            raise forms.ValidationError(
                f"No puedes dar de baja más de lo disponible en el lote ({self.lote.cantidad_disponible})."
            )
        return cantidad


class RecetaConversionForm(BaseModelForm):
    class Meta:
        model = RecetaConversion
        fields = ["producto_origen", "producto_destino", "cantidad_origen", "cantidad_destino", "limite_diario_origen"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un paquete no tiene lote propio que convertir (ver TraspasoForm).
        productos = Producto.objects.filter(is_active=True).exclude(tipo=Producto.TipoProducto.PAQUETE)
        self.fields["producto_origen"].queryset = productos
        self.fields["producto_destino"].queryset = productos
        self.fields["limite_diario_origen"].required = False


class ConversionForm(forms.Form):
    """No es un ModelForm: `Conversion.cantidad_destino_generada`,
    `valor_consumido` y `valor_generado` los calcula
    apps.inventario.services.registrar_conversion() -aquí solo se captura lo
    que de verdad decide la persona (qué receta, cuánto, en qué almacén)."""

    almacen = forms.ModelChoiceField(queryset=Almacen.objects.filter(is_active=True))
    receta = forms.ModelChoiceField(queryset=RecetaConversion.objects.filter(is_active=True))
    cantidad_origen = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), label="Cantidad de origen a convertir"
    )
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    observaciones = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        almacenes = Almacen.objects.filter(is_active=True)
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                almacenes = almacenes.filter(pk__in=visibles.values("pk"))
        self.fields["almacen"].queryset = almacenes
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
