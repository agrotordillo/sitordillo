from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.fiscal.models import FormaPago
from apps.pagos.models import CuentaPorPagar
from apps.products.models import Almacen, Producto
from apps.proveedores.models import Proveedor
from .models import OrdenCompra, OrdenCompraDetalle, PromocionProveedor


class PrecioUnitarioWidget(forms.NumberInput):
    """Muestra el precio recortando ceros de relleno (238.5000 -> 238.50),
    pero sin redondear ni esconder precisión real (66.7850 -> 66.785,
    66.7847 se queda igual) — el campo admite hasta 4 decimales, esto solo
    limpia cómo se ve cuando no hacen falta."""

    def format_value(self, value):
        if value in (None, ""):
            return super().format_value(value)
        try:
            valor = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return super().format_value(value)

        texto = format(valor, "f")
        if "." not in texto:
            return texto
        entero, _, decimales = texto.partition(".")
        decimales = decimales.rstrip("0")
        if len(decimales) < 2:
            decimales = decimales.ljust(2, "0")
        return f"{entero}.{decimales}"


class CargarCFDIForm(forms.Form):
    archivo = forms.FileField(label="Archivo XML del CFDI")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo"].widget.attrs["class"] = "input"

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xml"):
            raise forms.ValidationError("El archivo debe ser un .xml (el CFDI, no el PDF de la representación impresa).")
        return archivo


class OrdenCompraForm(BaseModelForm):
    class Meta:
        model = OrdenCompra
        fields = [
            "proveedor",
            "almacen_destino",
            "fecha_orden",
            "fecha_entrega_estimada",
            "estatus",
            "es_fiscal",
            "documento",
            "estado_pago",
            "medio_pago",
            "forma_pago",
            "descuento_pct",
            "iva",
            "ieps",
            "retencion_iva",
            "retencion_isr",
            "flete",
            "observaciones",
        ]
        widgets = {
            # El catálogo de proveedores ya no cabe en un <select>: se busca
            # por texto (ver proveedor-search.js) y este campo solo guarda
            # el id elegido.
            "proveedor": forms.HiddenInput,
            "fecha_orden": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_entrega_estimada": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    # Los únicos estatus que se eligen a mano: "Parcial" y "Recibida" los pone
    # la recepción (OrdenCompra.actualizar_estatus_por_recepcion), nunca la
    # persona (B20 en docs/AUDITORIA.md).
    ESTATUS_MANUALES = (OrdenCompra.Estatus.BORRADOR, OrdenCompra.Estatus.ENVIADA, OrdenCompra.Estatus.CANCELADA)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self._configurar_estatus_y_bloqueos()
        # Para que formset-rows.js y precio-alerta.js calculen con el mismo %
        # base que usará OrdenCompra.total, sin esperar a que se reseleccione
        # el proveedor (ver proveedor-search.js).
        descuento_base = self._descuento_base_en_pantalla()
        if descuento_base is not None:
            self.fields["proveedor"].widget.attrs["data-descuento"] = str(descuento_base)
        if self.instance.cfdi_uuid:
            # Su base siempre es 0 (ver OrdenCompra._descuento_base_vigente):
            # proveedor-search.js no debe tomar el del proveedor que se elija.
            self.fields["proveedor"].widget.attrs["data-sin-descuento-base"] = "true"
        self.fields["almacen_destino"].queryset = Almacen.objects.filter(is_active=True)
        self.fields["almacen_destino"].required = True
        if not self.instance.pk:
            self.fields["almacen_destino"].initial = Almacen.objects.filter(
                is_active=True, tipo=Almacen.Tipo.CEDIS
            ).first()
        self.fields["forma_pago"].queryset = FormaPago.objects.filter(is_active=True)
        self.fields["forma_pago"].required = False
        self.fields["descuento_pct"].widget.attrs.update({
            "class": (self.fields["descuento_pct"].widget.attrs.get("class", "") + " fs-descuento-general").strip(),
            "step": "0.01",
            "min": "0",
            "max": "100",
        })
        for campo in ("iva", "ieps"):
            self.fields[campo].widget.attrs.update({
                "class": (self.fields[campo].widget.attrs.get("class", "") + " fs-impuesto-suma").strip(),
                "step": "0.01",
                "min": "0",
            })
        for campo in ("retencion_iva", "retencion_isr"):
            self.fields[campo].widget.attrs.update({
                "class": (self.fields[campo].widget.attrs.get("class", "") + " fs-impuesto-resta").strip(),
                "step": "0.01",
                "min": "0",
            })
        # Sin fs-impuesto-suma: el flete no se paga al proveedor, así que no
        # debe sumarse al total/cuenta por pagar que calcula formset-rows.js.
        self.fields["flete"].widget.attrs.update({"step": "0.01", "min": "0"})

    def _configurar_estatus_y_bloqueos(self):
        """Una orden que ya tiene mercancía recibida solo admite cambios de
        precio y de datos de la factura (decisión del usuario, B20): su
        estatus lo lleva la recepción, y proveedor y almacén destino quedan
        fijos -la mercancía ya entró con ellos-. Sin recepciones, el estatus
        solo puede ser uno de ESTATUS_MANUALES."""
        orden = self.instance
        # Lo recibido de cada línea con lo que se decidió qué se puede
        # editar: OrdenCompraUpdateView lo compara, ya con la orden
        # bloqueada, contra lo de ese momento antes de guardar.
        self.recibido_al_cargar = (
            dict(orden.detalles.values_list("pk", "cantidad_recibida")) if orden.pk else {}
        )
        self.tiene_recepciones = any(recibido > 0 for recibido in self.recibido_al_cargar.values())
        if self.tiene_recepciones:
            for campo in ("estatus", "proveedor", "almacen_destino"):
                self.fields[campo].disabled = True
            self.fields["estatus"].help_text = "Ya hay mercancía recibida: el estatus lo actualiza la recepción."
            return
        manuales = list(self.ESTATUS_MANUALES)
        if not orden.pk:
            manuales.remove(OrdenCompra.Estatus.CANCELADA)
        elif orden.estatus not in manuales:
            # Una orden "Parcial" a la que una corrección le dejó todo en 0:
            # se conserva su estatus actual como opción.
            manuales.insert(0, orden.estatus)
        self.fields["estatus"].choices = [(e.value, e.label) for e in OrdenCompra.Estatus if e in manuales]

    def clean_estatus(self):
        estatus = self.cleaned_data["estatus"]
        orden = self.instance
        if (
            estatus == OrdenCompra.Estatus.CANCELADA
            and orden.pk
            and CuentaPorPagar.objects.filter(orden_compra=orden).exists()
        ):
            raise forms.ValidationError("No se puede cancelar una orden que ya tiene cuenta por pagar.")
        return estatus

    def _descuento_base_en_pantalla(self):
        """El % base del proveedor con el que se va a calcular esta orden:
        el congelado si se edita sin cambiar de proveedor, el vigente del
        proveedor elegido si es nueva o se cambió (también al volver a
        mostrar el formulario tras un error), y 0 en una orden de CFDI.
        None si todavía no hay proveedor."""
        orden = self.instance
        if self.is_bound:
            proveedor_id = str(self.data.get(self.add_prefix("proveedor")) or "").strip()
        else:
            proveedor_id = str(orden.proveedor_id or "")
        if not proveedor_id.isdigit():
            return None
        if orden.cfdi_uuid:
            return Decimal("0.00")
        if orden.pk and proveedor_id == str(orden.proveedor_id):
            return orden.descuento_base_pct
        return Proveedor.objects.filter(pk=proveedor_id).values_list("descuento", flat=True).first()


class OrdenCompraDetalleForm(BaseModelForm):
    class Meta:
        model = OrdenCompraDetalle
        fields = ["producto", "cantidad", "precio_unitario"]
        widgets = {
            # Con ~300 mil productos, un <select> normal es inviable: se
            # busca por texto (ver producto-search.js) y este campo solo
            # guarda el id elegido.
            "producto": forms.HiddenInput,
            "precio_unitario": PrecioUnitarioWidget,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un paquete no se compra a un proveedor: se ensambla internamente
        # a partir de productos que sí se compran.
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
        if self.instance.producto_id:
            # Precarga el costo anterior para que precio-alerta.js pueda
            # comparar sin esperar a que el usuario reseleccione el producto.
            self.fields["producto"].widget.attrs["data-precio-costo"] = str(self.instance.producto.precio_costo)
        if self.recibida:
            # Lo recibido ya entró al inventario con este producto: cambiarlo
            # aquí dejaría los lotes con otro producto que la orden (B20). El
            # producto equivocado se corrige en Lotes con "Corregir"
            # (inventario.services.corregir_recepcion).
            self.fields["producto"].disabled = True
        self.fields["cantidad"].widget.attrs.update({
            "class": (self.fields["cantidad"].widget.attrs.get("class", "") + " fs-cantidad").strip(),
            "step": "0.01",
            "min": "0.01",
        })
        self.fields["precio_unitario"].widget.attrs.update({
            "class": (self.fields["precio_unitario"].widget.attrs.get("class", "") + " fs-precio").strip(),
            "step": "0.0001",
            "min": "0",
        })

    @property
    def recibida(self):
        """Esta línea ya tiene mercancía recibida."""
        return bool(self.instance.pk) and self.instance.cantidad_recibida > 0

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if self.recibida and cantidad is not None and cantidad < self.instance.cantidad_recibida:
            raise forms.ValidationError(
                f"No puede ser menor a lo ya recibido ({self.instance.cantidad_recibida})."
            )
        return cantidad


class OrdenCompraDetalleBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        quitadas = [f for f in self.forms if f.recibida and self._should_delete_form(f)]
        if quitadas:
            productos = ", ".join(f.instance.producto.nombre for f in quitadas)
            raise forms.ValidationError(
                f"No se puede quitar una línea con mercancía ya recibida ({productos}). Si llegó otro producto, "
                "corrígelo en Lotes con \"Corregir\"."
            )


OrdenCompraDetalleFormSet = inlineformset_factory(
    OrdenCompra,
    OrdenCompraDetalle,
    form=OrdenCompraDetalleForm,
    formset=OrdenCompraDetalleBaseFormSet,
    extra=1,
    can_delete=True,
)


class PromocionProveedorForm(BaseModelForm):
    class Meta:
        model = PromocionProveedor
        fields = [
            "proveedor",
            "producto",
            "tipo_descuento",
            "descuento_porcentaje",
            "precio_promocional",
            "fecha_inicio",
            "fecha_fin",
            "observaciones",
        ]
        widgets = {
            "proveedor": forms.HiddenInput,
            "producto": forms.HiddenInput,
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
