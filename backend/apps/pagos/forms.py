from django import forms

from apps.core.forms import BaseModelForm
from apps.fiscal.models import FormaPago
from .models import Banco, Pago


class BancoForm(BaseModelForm):
    class Meta:
        model = Banco
        fields = ["nombre"]


class FormaPagoSelect(forms.Select):
    """Select de FormaPago con data-clave en cada <option>, para que
    pago-form.js muestre/oculte banco y número de referencia según la
    forma de pago elegida sin otra consulta al servidor."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._claves_por_id = dict(FormaPago.objects.values_list("pk", "clave"))

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        pk = value.value if hasattr(value, "value") else value
        clave = self._claves_por_id.get(pk)
        if clave:
            option["attrs"]["data-clave"] = clave
        return option


class GenerarCuentaForm(forms.Form):
    fecha_emision = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    observaciones = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()


class PagoMultipleForm(forms.Form):
    """Datos comunes de un pago que liquida varias cuentas por pagar del
    mismo proveedor a la vez (un solo cheque/transferencia/comprobante
    aplicado a cada cuenta seleccionada por su propio monto)."""

    fecha_pago = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    forma_pago = forms.ModelChoiceField(queryset=FormaPago.objects.all(), widget=FormaPagoSelect)
    banco = forms.ModelChoiceField(queryset=Banco.objects.filter(is_active=True), required=False)
    numero_referencia = forms.CharField(max_length=50, required=False)
    comprobante = forms.FileField(required=False)
    observaciones = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "comprobante":
                continue
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()

    def clean(self):
        cleaned = super().clean()
        forma_pago = cleaned.get("forma_pago")
        banco = cleaned.get("banco")
        numero_referencia = cleaned.get("numero_referencia")
        if forma_pago:
            clave = forma_pago.clave
            if clave == Pago.CLAVE_TRANSFERENCIA and not banco:
                self.add_error("banco", "Indica el banco de la transferencia.")
            if clave not in Pago.CLAVES_CON_BANCO and banco:
                self.add_error(
                    "banco", "El banco solo aplica cuando la forma de pago es transferencia o pago con tarjeta."
                )
            if clave in (Pago.CLAVE_CHEQUE, Pago.CLAVE_COMPENSACION) and not numero_referencia:
                etiqueta = "cheque" if clave == Pago.CLAVE_CHEQUE else "nota de crédito"
                self.add_error("numero_referencia", f"Indica el número de {etiqueta}.")
            if clave not in (Pago.CLAVE_CHEQUE, Pago.CLAVE_COMPENSACION) and numero_referencia:
                self.add_error(
                    "numero_referencia",
                    "Este número solo aplica para cheque nominativo o compensación (nota de crédito).",
                )
        return cleaned


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Receta documentada de Django para un campo de archivo múltiple: no
    existe un FileField nativo para varios archivos, así que se limpia cada
    uno con la lógica normal de FileField."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            resultado = [single_file_clean(d, initial) for d in data]
        else:
            resultado = [single_file_clean(data, initial)] if data else []
        if self.required and not resultado:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        return resultado


class EnviarComprobanteForm(forms.Form):
    """Correo de notificación de pago: el destinatario/CC son editables y
    los adjuntos siempre se suben en el momento (no se reutiliza el
    comprobante ya guardado del pago, para permitir mandar varios
    documentos juntos aunque el pago original solo tenga uno o ninguno)."""

    destinatario = forms.EmailField(label="Para")
    cc = forms.CharField(label="CC", required=False, help_text="Correos separados por coma (opcional)")
    adjuntos = MultipleFileField(label="Adjuntar documentos")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "adjuntos":
                continue
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()

    def clean_cc(self):
        crudo = self.cleaned_data.get("cc", "").strip()
        if not crudo:
            return []
        validador = forms.EmailField()
        correos = []
        for correo in crudo.split(","):
            correo = correo.strip()
            if not correo:
                continue
            try:
                validador.clean(correo)
            except forms.ValidationError:
                raise forms.ValidationError(f'"{correo}" no es un correo válido.')
            correos.append(correo)
        return correos


class PagoForm(BaseModelForm):
    class Meta:
        model = Pago
        fields = [
            "fecha_pago", "monto_pagado", "forma_pago", "banco", "numero_referencia",
            "comprobante", "aplica_descuento_pronto_pago", "observaciones",
        ]
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "forma_pago": FormaPagoSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["banco"].queryset = Banco.objects.filter(is_active=True)
        self.fields["banco"].required = False
        self.fields["numero_referencia"].required = False
        self.fields["comprobante"].required = False
