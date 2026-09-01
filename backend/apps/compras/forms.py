from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.fiscal.models import FormaPago
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        if self.instance.proveedor_id:
            # Para que precio-alerta.js pueda comparar contra el % base del
            # proveedor sin esperar a que se reseleccione (ver proveedor-search.js).
            self.fields["proveedor"].widget.attrs["data-descuento"] = str(self.instance.proveedor.descuento)
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


OrdenCompraDetalleFormSet = inlineformset_factory(
    OrdenCompra,
    OrdenCompraDetalle,
    form=OrdenCompraDetalleForm,
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
