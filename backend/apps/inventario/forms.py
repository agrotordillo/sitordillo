from django import forms
from django.forms import formset_factory

from apps.products.models import Almacen


class RecepcionLineaForm(forms.Form):
    detalle_id = forms.IntegerField(widget=forms.HiddenInput)
    cantidad_recibir = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    numero_lote = forms.CharField(max_length=50, required=False)
    fecha_caducidad = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    costo_unitario = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    almacen = forms.ModelChoiceField(queryset=Almacen.objects.filter(is_active=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} input".strip()
        self.fields["detalle_id"].widget.attrs["class"] = ""


RecepcionFormSet = formset_factory(RecepcionLineaForm, extra=0)
