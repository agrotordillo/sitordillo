from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseAbstractModel
from apps.core.permisos_estrictos import APPS_PERMISO_ESTRICTO, es_permiso_estricto, permisos_explicitos


class User(AbstractUser):
    """Igual que el usuario de Django, salvo que en los módulos de
    APPS_PERMISO_ESTRICTO (hoy Gastos) ser superusuario no basta: solo
    cuentan los permisos asignados de verdad. Al resolverse aquí, lo
    respetan sin cambios PermissionRequiredMixin, `user.has_perm()` y
    `{% if perms.gastos... %}` en menús y plantillas."""

    def has_perm(self, perm, obj=None):
        if es_permiso_estricto(perm):
            return perm in permisos_explicitos(self)
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if app_label in APPS_PERMISO_ESTRICTO:
            return any(perm.startswith(f"{app_label}.") for perm in permisos_explicitos(self))
        return super().has_module_perms(app_label)


class AsignacionSucursal(BaseAbstractModel):
    """A qué almacén(es) queda restringido un usuario (p. ej. un
    almacenista solo debe ver su propia sucursal). La mayoría de los
    usuarios tendrán una sola asignación marcada como principal, pero el
    modelo permite varias por usuario para el caso real de quien cubre
    turnos de descanso en distintas sucursales. Un usuario sin ninguna
    asignación no queda restringido por sucursal (es el caso esperado
    para Administrador y Auxiliar administrador, que ven todas)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asignaciones_sucursal",
        verbose_name="Usuario",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.CASCADE,
        related_name="usuarios_asignados",
        verbose_name="Almacén",
    )
    es_principal = models.BooleanField(
        default=True,
        verbose_name="Sucursal principal",
        help_text="La sucursal donde trabaja normalmente. Solo puede haber una principal por usuario.",
    )
    es_encargado = models.BooleanField(
        default=False,
        verbose_name="Encargado de esta sucursal",
        help_text="Supervisa al resto del personal de esta sucursal (sin poder de cancelar/autorizar, eso es exclusivo del Administrador).",
    )

    class Meta:
        verbose_name = "Asignación de sucursal"
        verbose_name_plural = "Asignaciones de sucursal"
        ordering = ["usuario", "-es_principal"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "almacen"], name="asu_unico_usuario_almacen"),
            # Fuente de verdad de "una sola principal" (B21 en
            # docs/AUDITORIA.md). Por ser condicional no se puede diferir:
            # al cambiar la principal, primero se desmarca la anterior (ver
            # accounts.forms.AsignacionSucursalBaseFormSet.save).
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(es_principal=True),
                name="asu_una_principal_por_usuario",
                violation_error_message="Este usuario ya tiene otra sucursal marcada como principal.",
            ),
        ]
        indexes = [
            models.Index(fields=["usuario"]),
            models.Index(fields=["almacen"]),
        ]

    def __str__(self):
        return f"{self.usuario.get_username()} · {self.almacen.nombre}"

    def get_folio_prefix(self):
        return "ASU"

    def get_slug_source(self):
        return f"{self.usuario_id}-{self.almacen_id}"

    @property
    def display_name(self):
        return self.__str__()

    # El formulario de usuario (sucursales en un formset) lo apaga: ahí la
    # regla se revisa sobre todas las filas juntas, y contra la BD daría un
    # falso choque al mover la principal de A a B en un mismo guardado.
    validar_principal_contra_bd = True

    def clean(self):
        super().clean()
        if self.es_principal and self.usuario_id and self.validar_principal_contra_bd:
            ya_tiene_principal = (
                AsignacionSucursal.objects.filter(usuario_id=self.usuario_id, es_principal=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if ya_tiene_principal:
                raise ValidationError({
                    "es_principal": "Este usuario ya tiene otra sucursal marcada como principal.",
                })
