from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseAbstractModel


class User(AbstractUser):
    pass


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

    def clean(self):
        super().clean()
        if self.es_principal and self.usuario_id:
            ya_tiene_principal = (
                AsignacionSucursal.objects.filter(usuario_id=self.usuario_id, es_principal=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if ya_tiene_principal:
                raise ValidationError({
                    "es_principal": "Este usuario ya tiene otra sucursal marcada como principal.",
                })
