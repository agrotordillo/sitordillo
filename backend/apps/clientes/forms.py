from apps.core.forms import BaseModelForm
from apps.products.models import ListaPrecio
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
            "direccion",
            "tiene_credito",
            "limite_credito",
            "dias_credito",
            "descuento",
            "lista_precio",
            "observaciones",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # El precio preferente del cliente (su lista de precio por default en
        # ventas/cotizaciones) es un invariante de negocio exclusivo del
        # Administrador (mismo criterio que SuperuserRequiredMixin): quien
        # no es superusuario ni siquiera ve el campo, así no puede dárselo
        # de alta ni cambiarlo desde este formulario.
        if user is not None and not user.is_superuser:
            self.fields.pop("lista_precio", None)
        elif "lista_precio" in self.fields:
            self.fields["lista_precio"].queryset = ListaPrecio.objects.filter(is_active=True)
