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

    # Ventas sí puede registrar/actualizar un cliente (lo necesita para
    # capturar sus datos fiscales al momento de facturar), pero el crédito
    # que se le otorga y su precio preferente son invariantes de negocio
    # exclusivos del Administrador (mismo criterio que
    # SuperuserRequiredMixin): quien no es superusuario ni siquiera ve
    # estos campos, así no puede dárselos de alta ni cambiarlos desde este
    # formulario -sea al crear o al editar, ClienteCreateView y
    # ClienteUpdateView le pasan `user` a este form por igual-.
    CAMPOS_SOLO_ADMINISTRADOR = ["tiene_credito", "limite_credito", "dias_credito", "descuento", "lista_precio"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and not user.is_superuser:
            for campo in self.CAMPOS_SOLO_ADMINISTRADOR:
                self.fields.pop(campo, None)
        elif "lista_precio" in self.fields:
            self.fields["lista_precio"].queryset = ListaPrecio.objects.filter(is_active=True)
