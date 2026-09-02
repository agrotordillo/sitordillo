from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from django.forms import inlineformset_factory

from apps.core.forms import BaseModelForm
from apps.products.models import Almacen
from .models import AsignacionSucursal


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'input',
            'autofocus': True,
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'input',
            'autocomplete': 'current-password',
        })


class AsignacionSucursalForm(BaseModelForm):
    class Meta:
        model = AsignacionSucursal
        fields = ["usuario", "almacen", "es_principal", "es_encargado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True)


class UsuarioCreateForm(UserCreationForm):
    """Alta de usuario, con sus capacidades (grupos) de una sola vez. La
    asignación de sucursal va aparte, como formset inline en la misma
    pantalla (ver AsignacionSucursalInlineFormSet)."""

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Capacidades",
        help_text="Puede tener varias a la vez (p. ej. la persona única de una sucursal chica).",
    )
    is_superuser = forms.BooleanField(
        required=False,
        label="Es Administrador",
        help_text="Acceso total al sistema, sin restricción de sucursal ni de capacidades.",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        self.fields["email"].required = False
        for name, field in self.fields.items():
            if name == "groups":
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "h-4 w-4 border border-gray-300 rounded-base text-primary-600 cursor-pointer"
            else:
                css_class = "input"
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data.get("is_superuser", False)
        # Necesita is_staff para poder usar /admin/ (gestión de Grupos);
        # sin esto un Administrador no podría entrar ahí.
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            user.groups.set(self.cleaned_data.get("groups") or [])
        return user


class AsignacionSucursalInlineForm(BaseModelForm):
    """Variante de AsignacionSucursalForm sin el campo `usuario`: se usa
    dentro del formset inline al crear un usuario, donde el usuario ya
    está implícito (es el que se está creando en la misma pantalla)."""

    class Meta:
        model = AsignacionSucursal
        fields = ["almacen", "es_principal", "es_encargado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["almacen"].queryset = Almacen.objects.filter(is_active=True)


AsignacionSucursalInlineFormSet = inlineformset_factory(
    get_user_model(),
    AsignacionSucursal,
    form=AsignacionSucursalInlineForm,
    fk_name="usuario",
    extra=1,
    can_delete=True,
)
