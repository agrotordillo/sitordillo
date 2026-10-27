from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.products.models import Almacen, Categoria, Clase, Linea
from .models import DIAS, TODOS_LOS_DIAS, ComisionColaboradorLinea

User = get_user_model()


class ComisionColaboradorLineaForm(BaseModelForm):
    dias = forms.MultipleChoiceField(
        label="Días de la semana",
        choices=[(str(i), nombre.capitalize()) for i, nombre in enumerate(DIAS)],
        widget=forms.CheckboxSelectMultiple,
        help_text=ComisionColaboradorLinea._meta.get_field("dias_semana").help_text,
    )

    class Meta:
        model = ComisionColaboradorLinea
        fields = [
            "colaborador", "alcance", "almacen", "linea", "categoria", "clase",
            "porcentaje", "porcentaje_otras_listas", "comisiona_precio_especial",
            "vigente_desde", "vigente_hasta", "observaciones",
        ]
        widgets = {
            "vigente_desde": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vigente_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dias"].initial = list(self.instance.dias_semana or TODOS_LOS_DIAS)
        # BaseModelForm le pone "input" a todo lo que no es un CheckboxInput suelto.
        self.fields["dias"].widget.attrs["class"] = "h-4 w-4 border border-gray-300 rounded-base text-primary-600 cursor-pointer"
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

    def clean(self):
        cleaned = super().clean()
        # Antes de que el modelo se valide (dias_semana es un texto "0123456").
        self.instance.dias_semana = "".join(sorted(cleaned.get("dias") or []))
        return cleaned
