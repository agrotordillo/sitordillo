from decimal import Decimal

from django import forms
from django.forms import formset_factory, inlineformset_factory

from apps.compras.models import OrdenCompra
from apps.core.forms import BaseModelForm
from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen, Producto
from apps.proveedores.models import Proveedor
from .models import MovimientoAlmacen, MovimientoAlmacenDetalle, RecetaConversion
from .services import impuestos_unitarios_de_linea


class RecepcionLineaForm(forms.Form):
    detalle_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad_recibir = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    numero_lote = forms.CharField(max_length=50, required=False)
    fecha_caducidad = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    costo_unitario = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    almacen = forms.ModelChoiceField(queryset=Almacen.objects.filter(is_active=True))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo se da entrada en una sucursal a la que el usuario está
        # asignado (B23 en docs/AUDITORIA.md); sin asignaciones (Compras
        # central, Administrador) ve todas.
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                self.fields["almacen"].queryset = self.fields["almacen"].queryset.filter(pk__in=visibles.values("pk"))
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
    # Lo que trae la nota de crédito del proveedor; la pantalla propone lo
    # que corresponde a la cantidad dañada según las tasas del producto, y
    # en blanco se toma esa misma sugerencia (B22 en docs/AUDITORIA.md).
    iva = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, label="IVA a descontar"
    )
    ieps = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, label="IEPS a descontar"
    )
    motivo = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, lote=None, **kwargs):
        self.lote = lote
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
        self.fields["cantidad"].widget.attrs["x-model"] = "cantidad"
        for campo in ("iva", "ieps"):
            self.fields[campo].widget.attrs.update({
                "x-model": campo, "@input": f"{campo}Editado = true", "step": "0.01", "min": "0",
            })

        # Datos para la sugerencia en pantalla (ver reportar_merma_form.html).
        self.orden = None
        iva_unitario = ieps_unitario = Decimal("0")
        detalle = lote.orden_compra_detalle if lote is not None else None
        if detalle is not None:
            self.orden = detalle.orden_compra
            iva_unitario, ieps_unitario = impuestos_unitarios_de_linea(detalle, self.orden)
        self.sugerencia = {
            "iva_unitario": format(iva_unitario, "f"),
            "ieps_unitario": format(ieps_unitario, "f"),
            "iva_orden": format(self.orden.iva if self.orden else Decimal("0"), "f"),
            "ieps_orden": format(self.orden.ieps if self.orden else Decimal("0"), "f"),
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if self.lote and cantidad > self.lote.cantidad_disponible:
            raise forms.ValidationError(
                f"No puedes dar de baja más de lo disponible en el lote ({self.lote.cantidad_disponible})."
            )
        return cantidad

    def _clean_impuesto(self, campo):
        monto = self.cleaned_data[campo]
        de_la_orden = getattr(self.orden, campo, None)
        if monto is not None and de_la_orden is not None and monto > de_la_orden:
            raise forms.ValidationError(f"No puede ser mayor al {campo.upper()} de la orden (${de_la_orden}).")
        return monto

    def clean_iva(self):
        return self._clean_impuesto("iva")

    def clean_ieps(self):
        return self._clean_impuesto("ieps")


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


class EnsamblePaqueteForm(forms.Form):
    """No es un ModelForm: `EnsamblePaquete.valor_consumido` y
    `valor_generado` los calcula
    apps.inventario.services.registrar_ensamble_paquete() -aquí solo se
    captura lo que de verdad decide la persona (qué paquete, cuánto, en
    qué almacén)."""

    almacen = forms.ModelChoiceField(queryset=Almacen.objects.filter(is_active=True))
    paquete = forms.ModelChoiceField(
        queryset=Producto.objects.filter(is_active=True, tipo=Producto.TipoProducto.PAQUETE),
        label="Paquete a armar",
    )
    cantidad = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), label="Cantidad a armar"
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

    def clean(self):
        cleaned_data = super().clean()
        paquete = cleaned_data.get("paquete")
        almacen = cleaned_data.get("almacen")
        if paquete and almacen and paquete.almacen_id != almacen.id:
            self.add_error(
                "almacen",
                f"El paquete '{paquete.nombre}' pertenece a la sucursal {paquete.almacen.nombre}; "
                "no se puede armar en otra.",
            )
        return cleaned_data


def conceptos_agrupados():
    """Opciones del concepto separadas en Entradas / Salidas (<optgroup>),
    igual que las ve Compras en la lista del sistema anterior."""
    entradas, salidas = [], []
    for valor, etiqueta in MovimientoAlmacen.Concepto.choices:
        (entradas if valor in MovimientoAlmacen.CONCEPTOS_ENTRADA else salidas).append((valor, etiqueta))
    return [("Entradas", entradas), ("Salidas", salidas)]


class MovimientoAlmacenForm(BaseModelForm):
    # La orden de compra y el movimiento que lo antecede se capturan por
    # folio (se tiene a la mano en la factura o en el documento anterior):
    # un <select> con todas las órdenes o movimientos sería inmanejable.
    orden_compra_folio = forms.CharField(
        max_length=20, required=False, label="Orden de compra relacionada (folio)"
    )
    movimiento_relacionado_folio = forms.CharField(
        max_length=20, required=False, label="Movimiento que lo antecede (folio)"
    )

    class Meta:
        model = MovimientoAlmacen
        fields = [
            "concepto",
            "almacen",
            "almacen_destino",
            "fecha",
            "proveedor",
            "documento_referencia",
            "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
            "concepto": forms.Select(attrs={"x-model": "concepto"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concepto"].choices = [("", "---------")] + conceptos_agrupados()
        almacenes = Almacen.objects.filter(is_active=True)
        if user is not None:
            visibles = almacenes_visibles(user)
            if visibles is not None:
                almacenes = almacenes.filter(pk__in=visibles.values("pk"))
        self.fields["almacen"].queryset = almacenes
        self.fields["almacen_destino"].queryset = Almacen.objects.filter(is_active=True).exclude(
            tipo=Almacen.Tipo.MOVIL
        )
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["fecha"].input_formats = ["%Y-%m-%d"]
        if self.instance.pk and not self.is_bound:
            if self.instance.orden_compra_id:
                self.fields["orden_compra_folio"].initial = self.instance.orden_compra.folio
            if self.instance.movimiento_relacionado_id:
                self.fields["movimiento_relacionado_folio"].initial = self.instance.movimiento_relacionado.folio

    def clean_orden_compra_folio(self):
        folio = self.cleaned_data["orden_compra_folio"].strip()
        if not folio:
            return None
        orden = OrdenCompra.objects.filter(folio__iexact=folio).first()
        if orden is None:
            raise forms.ValidationError(f"No existe una orden de compra con folio {folio}.")
        return orden

    def clean_movimiento_relacionado_folio(self):
        folio = self.cleaned_data["movimiento_relacionado_folio"].strip()
        if not folio:
            return None
        relacionado = MovimientoAlmacen.objects.filter(folio__iexact=folio).first()
        if relacionado is None:
            raise forms.ValidationError(f"No existe un movimiento de almacén con folio {folio}.")
        if self.instance.pk and relacionado.pk == self.instance.pk:
            raise forms.ValidationError("Un movimiento no puede relacionarse consigo mismo.")
        return relacionado

    def clean(self):
        cleaned = super().clean()
        # Campos que no aplican al concepto elegido se limpian en vez de
        # rechazarse: el formulario los oculta, pero pueden venir con un
        # valor que quedó de cuando se eligió otro concepto.
        concepto = cleaned.get("concepto")
        if concepto != MovimientoAlmacen.Concepto.SALIDA_DEVOLUCION_MOVIL:
            cleaned["almacen_destino"] = None
        if concepto not in MovimientoAlmacen.CONCEPTOS_CON_PROVEEDOR:
            cleaned["proveedor"] = None
        return cleaned

    def _post_clean(self):
        self.instance.orden_compra = self.cleaned_data.get("orden_compra_folio")
        self.instance.movimiento_relacionado = self.cleaned_data.get("movimiento_relacionado_folio")
        super()._post_clean()


class MovimientoAlmacenDetalleForm(BaseModelForm):
    class Meta:
        model = MovimientoAlmacenDetalle
        fields = ["producto", "cantidad"]
        widgets = {
            # Búsqueda por folio/SKU/código/nombre (ver producto-search.js),
            # igual que en traspasos.
            "producto": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un paquete no tiene lote propio: se mueven sus componentes.
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
        self.fields["cantidad"].widget.attrs.update({"step": "0.01", "min": "0.01"})


MovimientoAlmacenDetalleFormSet = inlineformset_factory(
    MovimientoAlmacen,
    MovimientoAlmacenDetalle,
    form=MovimientoAlmacenDetalleForm,
    extra=1,
    can_delete=True,
)
