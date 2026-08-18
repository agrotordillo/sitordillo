from django import forms

from apps.core.forms import BaseModelForm
from .models import Pago


class GenerarCuentaForm(forms.Form):
    fecha_emision = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    observaciones = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()


class PagoForm(BaseModelForm):
    class Meta:
        model = Pago
        fields = ["fecha_pago", "monto_pagado", "forma_pago", "aplica_descuento_pronto_pago", "observaciones"]
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
        }
