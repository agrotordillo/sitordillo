from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.products.models import Almacen, Categoria, Clase, Linea
from .models import ComisionColaboradorLinea

User = get_user_model()


class ComisionColaboradorLineaForm(BaseModelForm):
    class Meta:
        model = ComisionColaboradorLinea
        fields = [
            "colaborador", "almacen", "linea", "categoria", "clase",
            "porcentaje", "porcentaje_otras_listas", "observaciones",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # También los inactivos: los vendedores del sistema anterior son
        # usuarios sin acceso (ver apps.core.scv_web.VendedoresLegado) y sus
        # ventas históricas sí comisionan.
        self.fields["colaborador"].queryset = User.objects.order_by("-is_active", "first_name", "username")
        self.fields["colaborador"].label_from_instance = lambda u: (
            (u.get_full_name() or u.username) + ("" if u.is_active else " (sin acceso)")
        )
        self.fields["almacen"].queryset = Almacen.objects.order_by("nombre")
        self.fields["linea"].queryset = Linea.objects.filter(is_active=True)
        self.fields["categoria"].queryset = Categoria.objects.filter(is_active=True)
        self.fields["clase"].queryset = Clase.objects.filter(is_active=True)
