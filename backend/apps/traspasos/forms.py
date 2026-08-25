from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.products.models import Almacen, Producto
from .models import Traspaso, TraspasoDetalle


class TraspasoForm(BaseModelForm):
    class Meta:
        model = Traspaso
        fields = ["almacen_origen", "almacen_destino", "fecha_envio", "observaciones"]
        widgets = {
            "fecha_envio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El origen puede ser el CEDIS o una sucursal (traspaso entre
        # sucursales); el destino nunca puede ser el CEDIS (ver
        # Traspaso.clean()).
        self.fields["almacen_origen"].queryset = Almacen.objects.filter(is_active=True)
        self.fields["almacen_destino"].queryset = Almacen.objects.filter(is_active=True).exclude(
            tipo=Almacen.Tipo.CEDIS
        )


class TraspasoDetalleForm(BaseModelForm):
    class Meta:
        model = TraspasoDetalle
        fields = ["producto", "cantidad", "estrategia_salida"]
        widgets = {
            # Con miles de productos, un <select> normal es inviable: se
            # busca por folio/SKU/código/nombre (ver producto-search.js) y
            # este campo solo guarda el id elegido.
            "producto": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un paquete no tiene lote propio que traspasar; se traspasan sus
        # componentes por separado.
        self.fields["producto"].queryset = Producto.objects.filter(is_active=True).exclude(
            tipo=Producto.TipoProducto.PAQUETE
        )
        self.fields["cantidad"].widget.attrs.update({
            "class": (self.fields["cantidad"].widget.attrs.get("class", "") + " fs-cantidad").strip(),
            "step": "0.01",
            "min": "0.01",
        })


TraspasoDetalleFormSet = inlineformset_factory(
    Traspaso,
    TraspasoDetalle,
    form=TraspasoDetalleForm,
    extra=1,
    can_delete=True,
)
