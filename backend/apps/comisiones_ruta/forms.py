from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.products.models import Linea
from .models import ComisionColaboradorLinea

User = get_user_model()


class ComisionColaboradorLineaForm(BaseModelForm):
    class Meta:
        model = ComisionColaboradorLinea
        fields = ["colaborador", "linea", "porcentaje", "observaciones"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colaborador"].queryset = User.objects.filter(is_active=True).order_by(
            "first_name", "username"
        )
        self.fields["linea"].queryset = Linea.objects.filter(is_active=True)
