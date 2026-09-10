from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class ComisionLinea(BaseAbstractModel):
    """% de comisión base para cualquier producto de esta línea, para el
    reporte de comisiones de mostrador (ver comisiones.views.reporte_views).
    No hace falta capturarlo para todas las líneas, solo las que de verdad
    dan comisión -las demás simplemente no generan nada en el reporte."""

    linea = models.OneToOneField(
        "products.Linea",
        on_delete=models.CASCADE,
        related_name="comision",
        verbose_name="Línea",
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Comisión (%)")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Comisión por línea"
        verbose_name_plural = "Comisiones por línea"
        ordering = ["linea__nombre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(porcentaje__gte=0) & models.Q(porcentaje__lte=100),
                name="coml_porcentaje_rango_valido",
            ),
        ]

    def __str__(self):
        return f"{self.linea.nombre} · {self.porcentaje}%"

    def get_folio_prefix(self):
        return "COL"

    def get_slug_source(self):
        return f"{self.linea_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.porcentaje is not None and (self.porcentaje < 0 or self.porcentaje > 100):
            raise ValidationError({"porcentaje": "El porcentaje debe estar entre 0 y 100."})


class ComisionProducto(BaseAbstractModel):
    """% de comisión específico de un producto -tiene prioridad sobre el
    de su línea (ComisionLinea) cuando ambos existen-, para el caso de un
    producto puntual con una comisión distinta a la de su línea (p. ej.
    una promoción)."""

    producto = models.OneToOneField(
        "products.Producto",
        on_delete=models.CASCADE,
        related_name="comision",
        verbose_name="Producto",
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Comisión (%)")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Comisión por producto"
        verbose_name_plural = "Comisiones por producto"
        ordering = ["producto__nombre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(porcentaje__gte=0) & models.Q(porcentaje__lte=100),
                name="comp_porcentaje_rango_valido",
            ),
        ]

    def __str__(self):
        return f"{self.producto.nombre} · {self.porcentaje}%"

    def get_folio_prefix(self):
        return "COP"

    def get_slug_source(self):
        return f"{self.producto_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.porcentaje is not None and (self.porcentaje < 0 or self.porcentaje > 100):
            raise ValidationError({"porcentaje": "El porcentaje debe estar entre 0 y 100."})
