from apps.core.forms import BaseModelForm
from .models import Proveedor


class ProveedorForm(BaseModelForm):
    class Meta:
        model = Proveedor
        fields = [
            "tipo_persona",
            "rfc",
            "nombre_fiscal",
            "nombre_comercial",
            "regimen_fiscal",
            "tiene_credito",
            "limite_credito",
            "dias_credito",
            "descuento",
            "descuento_pronto_pago",
            "dias_pronto_pago",
            "contacto_nombre",
            "contacto_telefono",
            "contacto_email",
            "observaciones",
        ]
