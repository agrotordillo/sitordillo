from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from apps.core.forms import BaseModelForm
from apps.core.permisos_estrictos import grupos_protegidos, grupos_que_no_puede_otorgar
from apps.gastos.models import BitacoraAccesoGastos
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


AYUDA_ES_ADMINISTRADOR = (
    "Acceso total al sistema, sin restricción de sucursal ni de capacidades, excepto Gastos: ese módulo requiere "
    "su capacidad asignada aunque sea Administrador."
)


class _CapacidadesProtegidasMixin:
    """Las capacidades que dan acceso a un módulo estricto (hoy Gastos, ver
    apps.core.permisos_estrictos) solo las puede dar o quitar quien ya las
    tiene: un Administrador sin acceso a Gastos no puede asignárselo ni a sí
    mismo ni a otros. Esas capacidades no aparecen en su lista, y las que el
    usuario editado ya tenía se conservan tal cual al guardar. Cada cambio
    queda en la bitácora de acceso."""

    def _configurar_capacidades(self, solicitante):
        self.solicitante = solicitante
        bloqueadas = grupos_que_no_puede_otorgar(solicitante) if solicitante else grupos_protegidos()
        self._bloqueadas_ids = list(bloqueadas.values_list("pk", flat=True))
        self.fields["groups"].queryset = Group.objects.exclude(pk__in=self._bloqueadas_ids).order_by("name")
        self.capacidades_bloqueadas = (
            sorted(self.instance.groups.filter(pk__in=self._bloqueadas_ids).values_list("name", flat=True))
            if self.instance.pk else []
        )

    def _guardar_capacidades(self, user):
        protegidas_ids = list(grupos_protegidos().values_list("pk", flat=True))
        antes = set(user.groups.filter(pk__in=protegidas_ids))
        conservadas = list(user.groups.filter(pk__in=self._bloqueadas_ids))
        user.groups.set(list(self.cleaned_data.get("groups") or []) + conservadas)
        despues = set(user.groups.filter(pk__in=protegidas_ids))
        BitacoraAccesoGastos.registrar_cambios(user, antes, despues, realizado_por=self.solicitante)


class UsuarioCreateForm(_CapacidadesProtegidasMixin, UserCreationForm):
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
        help_text=AYUDA_ES_ADMINISTRADOR,
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, solicitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configurar_capacidades(solicitante)
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
        # Necesita is_staff para poder usar /admin/ (usuarios, grupos y
        # permisos ya no se gestionan ahí, ver accounts.admin).
        user.is_staff = user.is_superuser
        if commit:
            user.save()
            self._guardar_capacidades(user)
        return user


class UsuarioUpdateForm(_CapacidadesProtegidasMixin, forms.ModelForm):
    """Edición de un usuario existente: mismos campos de capacidades que
    UsuarioCreateForm. La contraseña es opcional aquí -dejarla en blanco no
    la toca-, a diferencia del alta donde siempre es obligatoria."""

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
        help_text=AYUDA_ES_ADMINISTRADOR,
    )
    password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput,
        required=False,
        help_text="Déjala en blanco para no cambiarla.",
    )
    password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, solicitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configurar_capacidades(solicitante)
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        self.fields["email"].required = False
        if self.instance and self.instance.pk:
            self.fields["is_superuser"].initial = self.instance.is_superuser
            self.fields["groups"].initial = self.instance.groups.all()
        if self._es_el_mismo_administrador():
            # Quitarse a sí mismo el acceso de Administrador lo dejaría fuera
            # de esta pantalla sin que nadie lo decida (B21): lo hace otro.
            self.fields["is_superuser"].disabled = True
            self.fields["is_superuser"].help_text = (
                "No puedes quitarte tu propio acceso de Administrador; pídeselo a otro Administrador."
            )
        if self.capacidades_bloqueadas:
            # Cambiarle la contraseña a quien tiene acceso a Gastos sería otra
            # forma de entrar al módulo sin tener la capacidad.
            for campo in ("password1", "password2"):
                self.fields[campo].disabled = True
            self.fields["password1"].help_text = (
                "Este usuario tiene acceso a Gastos: solo quien también tiene ese acceso puede cambiarle la contraseña."
            )
        for name, field in self.fields.items():
            if name == "groups":
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "h-4 w-4 border border-gray-300 rounded-base text-primary-600 cursor-pointer"
            else:
                css_class = "input"
            existing = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()

    def _es_el_mismo_administrador(self):
        return bool(
            self.solicitante
            and self.instance.pk
            and self.instance.pk == self.solicitante.pk
            and self.instance.is_superuser
        )

    def clean_is_superuser(self):
        es_superusuario = self.cleaned_data.get("is_superuser", False)
        if self._es_el_mismo_administrador() and not es_superusuario:
            raise forms.ValidationError("No puedes quitarte tu propio acceso de Administrador.")
        return es_superusuario

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if not password1 and not password2:
            return password2
        if password1 != password2:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        password_validation.validate_password(password1, self.instance)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = self.cleaned_data.get("is_superuser", False)
        # Necesita is_staff para poder usar /admin/ (usuarios, grupos y
        # permisos ya no se gestionan ahí, ver accounts.admin).
        user.is_staff = user.is_superuser
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)
        if commit:
            user.save()
            self._guardar_capacidades(user)
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

    def _post_clean(self):
        # "Una sola principal" la revisa AsignacionSucursalBaseFormSet.clean
        # sobre todas las filas juntas.
        self.instance.validar_principal_contra_bd = False
        super()._post_clean()


class AsignacionSucursalBaseFormSet(BaseInlineFormSet):
    def _filas_que_quedan(self):
        return [f for f in self.forms if f.cleaned_data and not self._should_delete_form(f)]

    def clean(self):
        super().clean()
        principales = [f for f in self._filas_que_quedan() if f.cleaned_data.get("es_principal")]
        if len(principales) > 1:
            nombres = ", ".join(f.cleaned_data["almacen"].nombre for f in principales if f.cleaned_data.get("almacen"))
            raise forms.ValidationError(f"Solo una sucursal puede ser la principal (marcaste: {nombres}).")

    def save(self, commit=True):
        if commit and self.instance.pk:
            # La restricción de una sola principal no puede diferirse: antes
            # de guardar las filas se desmarca la principal anterior si ya no
            # lo es, o marcar la nueva chocaría con ella.
            principal = next(
                (f.instance.pk for f in self._filas_que_quedan() if f.cleaned_data.get("es_principal")), None
            )
            (
                AsignacionSucursal.objects.filter(usuario=self.instance, es_principal=True)
                .exclude(pk=principal)
                .update(es_principal=False, updated_at=timezone.now())
            )
        return super().save(commit)


AsignacionSucursalInlineFormSet = inlineformset_factory(
    get_user_model(),
    AsignacionSucursal,
    form=AsignacionSucursalInlineForm,
    formset=AsignacionSucursalBaseFormSet,
    fk_name="usuario",
    extra=1,
    can_delete=True,
)
