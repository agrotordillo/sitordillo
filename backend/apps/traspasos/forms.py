from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.core.scoping import almacenes_visibles
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

    def __init__(self, *args, user=None, **kwargs):
        self._visibles = almacenes_visibles(user) if user is not None else None
        super().__init__(*args, **kwargs)
        # El origen puede ser el CEDIS o una sucursal (traspaso entre
        # sucursales); el destino nunca puede ser el CEDIS (ver
        # Traspaso.clean()).
        self.fields["almacen_origen"].queryset = Almacen.objects.filter(is_active=True)
        self.fields["almacen_destino"].queryset = Almacen.objects.filter(is_active=True).exclude(
            tipo=Almacen.Tipo.CEDIS
        )

    def clean(self):
        cleaned = super().clean()
        # Un traspaso conecta dos almacenes -no tiene sentido acotar el
        # <select> de cada lado a "solo su sucursal", porque el otro
        # extremo (CEDIS u otra sucursal) legítimamente no es suyo-, así
        # que en vez de restringir el queryset se valida que al menos uno
        # de los dos extremos sea de un usuario restringido.
        if self._visibles is not None:
            origen = cleaned.get("almacen_origen")
            destino = cleaned.get("almacen_destino")
            visibles_ids = set(self._visibles.values_list("pk", flat=True))
            if origen and destino and origen.pk not in visibles_ids and destino.pk not in visibles_ids:
                raise forms.ValidationError(
                    "El origen o el destino del traspaso debe ser una de tus sucursales asignadas."
                )
        return cleaned


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
