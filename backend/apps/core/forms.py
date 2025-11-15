# django imports
from django import forms

class BaseForm(forms.ModelForm):
    """
    Formulario base para todo el sistema.
    Configura estilos y comportamientos globales.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            field.widget.attrs.setdefault("placeholder", field.label)
            # Aquí podrás agregar Tailwind classes personalizadas si luego decides hacerlo
            # field.widget.attrs.setdefault("class", "form-input block w-full")
