from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class ComisionColaboradorLinea(BaseAbstractModel):
    """Regla de comisión de UN colaborador para el reporte de comisión por
    colaborador (ver comisiones_ruta.views.reporte_views). A diferencia de la
    comisión de mostrador (apps.comisiones.ComisionLinea, igual para cualquier
    empleado), aquí cada colaborador tiene sus propias reglas -así lo maneja
    el negocio desde antes, en el Excel de comisiones (datos/COMISIONES
    P36.xlsx)-.

    Qué ventas cuenta la regla:
      - De quién: sin `almacen`, las que vendió el propio colaborador; con
        `almacen`, TODAS las de esa sucursal, las haya vendido quien sea (p.
        ej. el MVZ cobra el 4% de toda la farmacia de clase MÉDICOS de LERDO).
      - De qué: los productos de su `linea`, `categoria` y `clase` (los que
        estén capturados; ninguno = todo lo vendido).
    Si varias reglas del mismo colaborador aplican a una línea de venta,
    gana la más específica (categoría, luego clase, luego línea): p. ej.
    FARMACIA 5% pero SOBRES (categoría) 10%.

    `porcentaje` aplica a ventas en PUBLICO y MEDIO MAYOREO;
    `porcentaje_otras_listas` a cualquier otra (MAYOREO, SUB DISTRIBUIDOR,
    PROMOCION): 1% en casi todos -así lo confirmaron las fórmulas del Excel-,
    0% para quien solo comisiona P1-P2 y el mismo % para quien comisiona
    sobre toda su venta."""

    colaborador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comisiones_ruta",
        verbose_name="Colaborador",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comisiones_ruta",
        verbose_name="Sobre la venta de la sucursal",
        help_text="Vacío: solo lo que vende el colaborador. Con sucursal: toda la venta de esa sucursal, "
        "la haya hecho quien sea.",
    )
    linea = models.ForeignKey(
        "products.Linea",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comisiones_ruta",
        verbose_name="Línea",
        help_text="Vacío: todas las líneas.",
    )
    categoria = models.ForeignKey(
        "products.Categoria",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comisiones_ruta",
        verbose_name="Categoría",
    )
    clase = models.ForeignKey(
        "products.Clase",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comisiones_ruta",
        verbose_name="Clase",
    )
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Comisión PUBLICO / MEDIO MAYOREO (%)"
    )
    porcentaje_otras_listas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Comisión en otras listas (%)",
        help_text="MAYOREO, SUB DISTRIBUIDOR y PROMOCION.",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Comisión por colaborador"
        verbose_name_plural = "Comisiones por colaborador"
        ordering = ["colaborador__first_name", "colaborador__username", "linea__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["colaborador", "almacen", "linea", "categoria", "clase"],
                nulls_distinct=False,
                name="ccl_unica_regla_colaborador",
                violation_error_message="Este colaborador ya tiene una regla con esa misma sucursal, línea, "
                "categoría y clase.",
            ),
            models.CheckConstraint(
                condition=models.Q(porcentaje__gte=0) & models.Q(porcentaje__lte=100),
                name="ccl_porcentaje_rango_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(porcentaje_otras_listas__gte=0) & models.Q(porcentaje_otras_listas__lte=100),
                name="ccl_porcentaje_otras_rango_valido",
            ),
        ]

    def __str__(self):
        return f"{self.colaborador.get_full_name() or self.colaborador.username} · {self.descripcion} · {self.porcentaje}%"

    def get_folio_prefix(self):
        return "CCL"

    def get_slug_source(self):
        return f"{self.colaborador_id}-{self.almacen_id}-{self.linea_id}-{self.categoria_id}-{self.clase_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def descripcion(self):
        """Qué cuenta la regla, en palabras: "FARMACIA · clase MEDICOS · venta de LERDO"."""
        partes = [self.linea.nombre if self.linea_id else "Todas las líneas"]
        if self.categoria_id:
            partes.append(f"categoría {self.categoria.nombre}")
        if self.clase_id:
            partes.append(f"clase {self.clase.nombre}")
        if self.almacen_id:
            partes.append(f"venta de {self.almacen.nombre}")
        return " · ".join(partes)

    @property
    def especificidad(self):
        """Para elegir entre varias reglas que aplican: gana la mayor."""
        return (4 if self.categoria_id else 0) + (2 if self.clase_id else 0) + (1 if self.linea_id else 0)

    def aplica_a(self, producto):
        return (
            (not self.linea_id or producto.linea_id == self.linea_id)
            and (not self.categoria_id or producto.categoria_id == self.categoria_id)
            and (not self.clase_id or producto.clase_id == self.clase_id)
        )

    def clean(self):
        super().clean()
        for campo in ("porcentaje", "porcentaje_otras_listas"):
            valor = getattr(self, campo)
            if valor is not None and (valor < 0 or valor > 100):
                raise ValidationError({campo: "El porcentaje debe estar entre 0 y 100."})
