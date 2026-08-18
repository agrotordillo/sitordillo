from apps.core.forms import BaseModelForm
from .models import Cliente


class ClienteForm(BaseModelForm):
    class Meta:
        model = Cliente
        fields = [
            "nombre",
            "tipo_persona",
            "rfc",
            "nombre_fiscal",
            "regimen_fiscal",
            "uso_cfdi",
            "codigo_postal",
            "contacto_telefono",
            "contacto_email",
            "tiene_credito",
            "limite_credito",
            "dias_credito",
            "descuento",
            "observaciones",
        ]
