from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import BaseAbstractModel


class CentroCosto(BaseAbstractModel):
    """A dónde se le carga un gasto. Generaliza a `products.Almacen`: una
    sucursal de venta es un centro de costo (ligado a su Almacen, para poder
    cruzar su gasto contra `ventas.Venta` y calcular el punto de equilibrio),
    pero también existen centros que no venden y aun así deben llevar su
    propio control de gasto -por ejemplo, para la declaración fiscal del
    PFAE que agrupa todas las actividades del negocio- como proyectos
    agropecuarios, administración corporativa o gasto personal de los
    dueños."""

    class Tipo(models.TextChoices):
        SUCURSAL = "sucursal", "Sucursal (venta al público)"
        PROYECTO = "proyecto", "Proyecto / actividad no comercial"
        ADMINISTRATIVO = "administrativo", "Administración / corporativo"
        PERSONAL = "personal", "Gasto personal de los dueños"

    codigo = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código corto",
        help_text="Identificador corto para reconocerlo rápido en reportes (p. ej. \"01\" o \"SUR\"). Opcional.",
    )
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, verbose_name="Tipo de centro de costo")
    almacen = models.OneToOneField(
        "products.Almacen",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="centro_costo",
        verbose_name="Sucursal (almacén)",
        help_text="Obligatorio y único para centros de tipo Sucursal; no aplica a los demás tipos.",
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Centro de costo"
        verbose_name_plural = "Centros de costo"
        ordering = ["codigo", "nombre"]
        indexes = [
            models.Index(fields=["tipo"]),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}" if self.codigo else self.nombre

    def get_folio_prefix(self):
        return "CCO"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.codigo == "":
            self.codigo = None
        if self.tipo == self.Tipo.SUCURSAL:
            if not self.almacen_id:
                raise ValidationError({"almacen": "Un centro de costo de tipo Sucursal debe ligarse a un almacén."})
            if self.almacen.tipo != self.almacen.Tipo.SUCURSAL:
                raise ValidationError({"almacen": "El almacén ligado debe ser de tipo Sucursal, no CEDIS."})
        elif self.almacen_id:
            raise ValidationError({"almacen": "Solo los centros de tipo Sucursal se ligan a un almacén."})


class CategoriaGasto(BaseAbstractModel):
    """Catálogo de clasificación operativa del gasto (servicios, personal,
    mobiliario, transporte, arrendamiento, etc.). Es un catálogo libre para
    poder agregar categorías nuevas sin tocar código."""

    class Naturaleza(models.TextChoices):
        FIJO = "fijo", "Fijo"
        VARIABLE = "variable", "Variable"

    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de la categoría",
        error_messages={"unique": "Ya existe una %(model_name)s con este nombre."},
    )
    naturaleza = models.CharField(
        max_length=10,
        choices=Naturaleza.choices,
        default=Naturaleza.VARIABLE,
        verbose_name="Naturaleza",
        help_text="Fijo: no depende de cuánto se venda (renta, internet). Variable: depende del nivel de operación.",
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Categoría de gasto"
        verbose_name_plural = "Categorías de gasto"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "CAT"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Gasto(BaseAbstractModel):
    """Un gasto registrado contra un centro de costo. Cuando `es_compartido`
    es verdadero, el importe no se contabiliza directamente al centro de
    costo de origen: se reparte entre las sucursales beneficiadas mediante
    `GastoDistribucion`, con montos exactos capturados a mano (nunca un
    promedio automático), porque el consumo real de cada sucursal no es
    proporcional -por ejemplo, el reparto de agua depende de cuánto
    personal tiene cada una, no de una división en partes iguales."""

    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.PROTECT,
        related_name="gastos",
        verbose_name="Centro de costo de origen",
        help_text="Quién generó/pagó el gasto. Si es compartido, aquí se registra el centro de origen (p. ej. Administración) y el detalle real por sucursal va en la distribución.",
    )
    categoria = models.ForeignKey(
        CategoriaGasto,
        on_delete=models.PROTECT,
        related_name="gastos",
        verbose_name="Categoría",
    )
    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
        verbose_name="Proveedor",
    )
    concepto = models.CharField(max_length=255, verbose_name="Concepto")
    responsable = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Responsable",
        help_text="Quién recibió o autorizó el gasto (nombre libre; no necesariamente un usuario del sistema).",
    )
    fecha = models.DateField(verbose_name="Fecha del gasto")
    importe = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Importe total")
    facturado = models.BooleanField(default=False, verbose_name="Facturado (con CFDI)")
    referencia_factura = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Referencia de factura",
        help_text="Folio o UUID fiscal, cuando el gasto está facturado.",
    )
    comprobante = models.FileField(
        upload_to="gastos/comprobantes/",
        null=True,
        blank=True,
        verbose_name="Comprobante",
    )
    es_compartido = models.BooleanField(
        default=False,
        verbose_name="Se distribuye entre varias sucursales",
        help_text="Actívalo cuando el gasto beneficia a más de una sucursal (p. ej. un servicio corporativo) y necesites repartirlo con montos exactos.",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-fecha", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(importe__gt=0), name="gto_importe_positivo"),
        ]
        indexes = [
            models.Index(fields=["centro_costo"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.concepto}"

    def get_folio_prefix(self):
        return "GTO"

    def get_slug_source(self):
        return f"{self.folio}-{self.centro_costo_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def monto_distribuido(self):
        return sum((d.monto for d in self.distribuciones.all()), Decimal("0.00"))

    @property
    def distribucion_cuadra(self):
        if not self.es_compartido:
            return True
        return self.monto_distribuido == self.importe

    def clean(self):
        super().clean()
        if self.importe is not None and self.importe <= 0:
            raise ValidationError({"importe": "El importe debe ser mayor a cero."})
        if self.facturado and not self.referencia_factura:
            raise ValidationError({"referencia_factura": "Indica el folio o UUID fiscal de la factura."})
        if not self.facturado and self.referencia_factura:
            raise ValidationError({"referencia_factura": "Solo aplica cuando el gasto está facturado."})


class GastoDistribucion(BaseAbstractModel):
    """Monto exacto de un gasto compartido que le corresponde a una
    sucursal. La suma de todas las distribuciones de un mismo `Gasto` debe
    ser exactamente igual a `Gasto.importe` (se valida al guardar, no es un
    promedio calculado)."""

    gasto = models.ForeignKey(
        Gasto,
        on_delete=models.CASCADE,
        related_name="distribuciones",
        verbose_name="Gasto",
    )
    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.PROTECT,
        related_name="distribuciones_gasto",
        verbose_name="Sucursal beneficiada",
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto asignado")

    class Meta:
        verbose_name = "Distribución de gasto"
        verbose_name_plural = "Distribuciones de gasto"
        constraints = [
            models.CheckConstraint(condition=models.Q(monto__gt=0), name="gtd_monto_positivo"),
            models.UniqueConstraint(fields=["gasto", "centro_costo"], name="gtd_unico_por_gasto_y_centro"),
        ]
        indexes = [
            models.Index(fields=["gasto"]),
            models.Index(fields=["centro_costo"]),
        ]

    def __str__(self):
        return f"{self.centro_costo.nombre} · ${self.monto}"

    def get_folio_prefix(self):
        return "GTD"

    def get_slug_source(self):
        return f"{self.gasto_id}-{self.centro_costo_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.monto is not None and self.monto <= 0:
            raise ValidationError({"monto": "El monto asignado debe ser mayor a cero."})
