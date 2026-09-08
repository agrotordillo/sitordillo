from django import forms

from apps.core.forms import BaseModelForm
from apps.pagos.forms import FormaPagoSelect
from apps.pagos.models import Banco
from .models import Cobro


class CobroForm(BaseModelForm):
    class Meta:
        model = Cobro
        fields = [
            "fecha_cobro", "monto_cobrado", "forma_pago", "banco", "numero_referencia",
            "comprobante", "observaciones",
        ]
        widgets = {
            "fecha_cobro": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "forma_pago": FormaPagoSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["banco"].queryset = Banco.objects.filter(is_active=True)
        self.fields["banco"].required = False
        self.fields["numero_referencia"].required = False
        self.fields["comprobante"].required = False
