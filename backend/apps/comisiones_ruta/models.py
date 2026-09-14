from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class ComisionColaboradorLinea(BaseAbstractModel):
    """% de comisión de UN colaborador (vendedor de ruta, uno por plaza) para
    una línea de producto, para el reporte de comisión por colaborador (ver
    comisiones_ruta.views.reporte_views). A diferencia de la comisión de
    mostrador (apps.comisiones.ComisionLinea, igual para cualquier empleado),
    aquí cada colaborador tiene su propio % -así lo maneja el negocio desde
    antes, en el Excel de comisiones-.

    Este % solo aplica a ventas en las listas de precio PUBLICO y MEDIO
    MAYOREO; las ventas en MAYOREO/SUB DISTRIBUIDOR/PROMOCION siempre
    comisionan 1% fijo sin importar este valor (ver PORCENTAJE_LISTAS_FIJAS
    en el reporte) -así lo confirmaron, sin excepción, las fórmulas de las
    14 hojas del Excel legado."""

    colaborador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comisiones_ruta",
        verbose_name="Colaborador",
    )
    linea = models.ForeignKey(
        "products.Linea",
        on_delete=models.CASCADE,
        related_name="comisiones_ruta",
        verbose_name="Línea",
    )
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Comisión (%)")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Comisión por colaborador"
        verbose_name_plural = "Comisiones por colaborador"
        ordering = ["colaborador__first_name", "colaborador__username", "linea__nombre"]
        constraints = [
            models.UniqueConstraint(fields=["colaborador", "linea"], name="ccl_unico_colaborador_linea"),
            models.CheckConstraint(
                condition=models.Q(porcentaje__gte=0) & models.Q(porcentaje__lte=100),
                name="ccl_porcentaje_rango_valido",
            ),
        ]

    def __str__(self):
        return f"{self.colaborador.get_full_name() or self.colaborador.username} · {self.linea.nombre} · {self.porcentaje}%"

    def get_folio_prefix(self):
        return "CCL"

    def get_slug_source(self):
        return f"{self.colaborador_id}-{self.linea_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.porcentaje is not None and (self.porcentaje < 0 or self.porcentaje > 100):
            raise ValidationError({"porcentaje": "El porcentaje debe estar entre 0 y 100."})
