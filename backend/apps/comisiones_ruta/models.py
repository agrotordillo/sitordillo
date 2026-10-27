from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel

TODOS_LOS_DIAS = "0123456"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class ComisionColaboradorLinea(BaseAbstractModel):
    """Regla de comisión de UN colaborador para el reporte de comisión por
    colaborador (ver comisiones_ruta.views.reporte_views). A diferencia de la
    comisión de mostrador (apps.comisiones.ComisionLinea, igual para cualquier
    empleado), aquí cada colaborador tiene sus propias reglas -así lo maneja
    el negocio desde antes, en el Excel de comisiones (datos/COMISIONES
    P36.xlsx)-.

    Qué ventas cuenta la regla (`alcance`):
      - PROPIAS: las que vendió el colaborador, en cualquier sucursal.
      - PROPIAS_EN_SUCURSAL: las que vendió él en `almacen` (p. ej. JHONY
        cobra distinto en IQUINUAPA, TECOLUTILLA y LERDO).
      - SUCURSAL: TODAS las de `almacen`, las haya vendido quien sea (p. ej.
        el MVZ cobra el 4% de toda la farmacia de clase MÉDICOS de LERDO).
    Y de qué: los productos de su `linea`, `categoria` y `clase` (los que
    estén capturados; ninguno = todo lo vendido). Si varias reglas del mismo
    colaborador aplican a una línea de venta, gana la más específica
    (categoría, luego clase, luego línea; a igualdad, la de una sucursal
    sobre la general): p. ej. FARMACIA 5% pero SOBRES (categoría) 10%.

    `porcentaje` aplica a ventas en PUBLICO y MEDIO MAYOREO;
    `porcentaje_otras_listas` a cualquier otra (MAYOREO, SUB DISTRIBUIDOR,
    PROMOCION): 1% en casi todos -así lo confirmaron las fórmulas del Excel-,
    0% para quien solo comisiona P1-P2 y el mismo % para quien comisiona
    sobre toda su venta. Lo cobrado con precio especial de sucursal
    (VentaDetalle.precio_especial) solo cuenta si `comisiona_precio_especial`:
    en el Excel esos precios (Precio 6-9) no salen en los bloques por línea,
    solo en los esquemas sobre toda la venta.

    `vigente_desde`/`vigente_hasta` y `dias_semana` dicen cuándo aplica: una
    regla sobre toda la venta de una sucursal no aplica el día de descanso del
    colaborador (ese día cobra quien lo cubre), y una suplencia (TARACENA en
    las vacaciones de MIGUEL) solo en sus fechas."""

    class Alcance(models.TextChoices):
        PROPIAS = "propias", "Sus ventas"
        PROPIAS_EN_SUCURSAL = "propias_sucursal", "Sus ventas en una sucursal"
        SUCURSAL = "sucursal", "Toda la venta de una sucursal"

    colaborador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comisiones_ruta",
        verbose_name="Colaborador",
    )
    alcance = models.CharField(
        max_length=20,
        choices=Alcance.choices,
        default=Alcance.PROPIAS,
        verbose_name="Sobre qué ventas",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comisiones_ruta",
        verbose_name="Sucursal",
        help_text="Solo para \"sus ventas en una sucursal\" y \"toda la venta de una sucursal\".",
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
    comisiona_precio_especial = models.BooleanField(
        default=False,
        verbose_name="Incluye ventas con precio especial de sucursal",
        help_text="En el Excel de comisiones solo las incluyen los esquemas sobre toda la venta (un % de todo).",
    )
    vigente_desde = models.DateField(null=True, blank=True, verbose_name="Vigente desde")
    vigente_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vigente hasta",
        help_text="Vacías: siempre. Para suplencias (p. ej. quien cubre las vacaciones de otro).",
    )
    dias_semana = models.CharField(
        max_length=7,
        default=TODOS_LOS_DIAS,
        verbose_name="Días de la semana",
        help_text="Los días en que aplica, 0 = lunes ... 6 = domingo: sin el día de descanso en las reglas "
        "sobre toda la venta de una sucursal (ese día cobra quien cubre).",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Comisión por colaborador"
        verbose_name_plural = "Comisiones por colaborador"
        ordering = ["colaborador__first_name", "colaborador__username", "linea__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["colaborador", "alcance", "almacen", "linea", "categoria", "clase", "vigente_desde"],
                nulls_distinct=False,
                name="ccl_unica_regla_colaborador",
                violation_error_message="Este colaborador ya tiene una regla con ese mismo alcance, sucursal, "
                "línea, categoría, clase y vigencia.",
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
        if self.alcance == self.Alcance.PROPIAS_EN_SUCURSAL and self.almacen_id:
            partes.append(f"sus ventas en {self.almacen.nombre}")
        elif self.alcance == self.Alcance.SUCURSAL and self.almacen_id:
            partes.append(f"toda la venta de {self.almacen.nombre}")
        if self.comisiona_precio_especial:
            partes.append("incluye precio especial")
        if self.dias_semana and self.dias_semana != TODOS_LOS_DIAS:
            faltan = [DIAS[int(d)] for d in TODOS_LOS_DIAS if d not in self.dias_semana]
            presentes = [DIAS[int(d)] for d in self.dias_semana]
            partes.append(f"sin {', '.join(faltan)}" if len(faltan) <= 2 else f"solo {', '.join(presentes)}")
        if self.vigente_desde or self.vigente_hasta:
            desde = f"{self.vigente_desde:%d/%m/%Y}" if self.vigente_desde else "…"
            hasta = f"{self.vigente_hasta:%d/%m/%Y}" if self.vigente_hasta else "…"
            partes.append(f"del {desde} al {hasta}")
        return " · ".join(partes)

    def aplica_en(self, fecha):
        """Si la regla está vigente en `fecha` (date) y ese día de la semana."""
        return (
            (self.vigente_desde is None or fecha >= self.vigente_desde)
            and (self.vigente_hasta is None or fecha <= self.vigente_hasta)
            and str(fecha.weekday()) in (self.dias_semana or TODOS_LOS_DIAS)
        )

    @property
    def especificidad(self):
        """Para elegir entre varias reglas que aplican: gana la mayor
        (categoría, luego clase, luego línea; a igualdad, la de sus ventas en
        una sucursal, luego la de sus ventas y al final la de toda la
        sucursal)."""
        catalogo = (4 if self.categoria_id else 0) + (2 if self.clase_id else 0) + (1 if self.linea_id else 0)
        prioridad = {self.Alcance.PROPIAS_EN_SUCURSAL: 2, self.Alcance.PROPIAS: 1, self.Alcance.SUCURSAL: 0}
        return catalogo, prioridad[self.alcance]

    def aplica_a(self, producto):
        return (
            (not self.linea_id or producto.linea_id == self.linea_id)
            and (not self.categoria_id or producto.categoria_id == self.categoria_id)
            and (not self.clase_id or producto.clase_id == self.clase_id)
        )

    def clean(self):
        super().clean()
        if self.alcance == self.Alcance.PROPIAS and self.almacen_id:
            raise ValidationError({"almacen": "Para \"sus ventas\" en cualquier sucursal, deja la sucursal vacía."})
        if self.alcance != self.Alcance.PROPIAS and not self.almacen_id:
            raise ValidationError({"almacen": "Elige la sucursal."})
        if self.vigente_desde and self.vigente_hasta and self.vigente_hasta < self.vigente_desde:
            raise ValidationError({"vigente_hasta": "No puede ser anterior a \"vigente desde\"."})
        if not self.dias_semana or any(d not in TODOS_LOS_DIAS for d in self.dias_semana):
            raise ValidationError({"dias_semana": "Elige al menos un día de la semana."})
        for campo in ("porcentaje", "porcentaje_otras_listas"):
            valor = getattr(self, campo)
            if valor is not None and (valor < 0 or valor > 100):
                raise ValidationError({campo: "El porcentaje debe estar entre 0 y 100."})
