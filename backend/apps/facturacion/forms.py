from django import forms

from apps.core.forms import BaseModelForm
from .models import Empresa


class EmpresaForm(BaseModelForm):
    class Meta:
        model = Empresa
        fields = [
            "tipo_persona",
            "rfc",
            "nombre_fiscal",
            "nombre_comercial",
            "regimen_fiscal",
            "codigo_postal",
            "telefono",
            "email",
            "serie_default",
        ]


class GenerarFacturaForm(forms.Form):
    uso_cfdi = forms.ModelChoiceField(queryset=None, label="Uso de CFDI")
    metodo_pago = forms.ModelChoiceField(queryset=None, label="Método de pago")
    serie = forms.CharField(max_length=10, required=False, help_text="Deja en blanco para usar la serie por omisión.")
    observaciones = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, **kwargs):
        from apps.fiscal.models import MetodoPago, UsoCFDI

        super().__init__(*args, **kwargs)
        self.fields["uso_cfdi"].queryset = UsoCFDI.objects.filter(is_active=True)
        self.fields["metodo_pago"].queryset = MetodoPago.objects.filter(is_active=True)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
