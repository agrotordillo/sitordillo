from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.fiscal.models import FormaPago
from apps.products.models import Producto
from apps.proveedores.models import Proveedor
from .models import OrdenCompra, OrdenCompraDetalle, PromocionProveedor


class OrdenCompraForm(BaseModelForm):
    class Meta:
        model = OrdenCompra
        fields = [
            "proveedor",
            "fecha_orden",
            "fecha_entrega_estimada",
            "estatus",
            "es_fiscal",
            "documento",
            "estado_pago",
            "medio_pago",
            "forma_pago",
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
            "fecha_orden": forms.DateInput(attrs={"type": "date"}),
            "fecha_entrega_estimada": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["forma_pago"].queryset = FormaPago.objects.filter(is_active=True)
        self.fields["forma_pago"].required = False
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un paquete no se compra a un proveedor: se ensambla internamente
        # a partir de productos que sí se compran.
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
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
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(is_active=True)
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
