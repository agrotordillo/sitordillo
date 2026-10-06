from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from apps.core.models import BaseAbstractModel
from apps.core.validators import RFC_PATTERN


class Empresa(BaseAbstractModel):
    """Datos fiscales propios del negocio (el Emisor de cada CFDI).
    Se espera un único registro; la UI lo trata como una ficha de
    configuración, no como un catálogo con altas múltiples."""

    class TipoPersona(models.TextChoices):
        FISICA = "fisica", "Persona física"
        MORAL = "moral", "Persona moral"

    tipo_persona = models.CharField(max_length=10, choices=TipoPersona.choices, verbose_name="Tipo de persona")
    rfc = models.CharField(
        max_length=13,
        unique=True,
        verbose_name="RFC",
        error_messages={"unique": "Ya existe un %(model_name)s con este RFC."},
    )
    nombre_fiscal = models.CharField(max_length=255, verbose_name="Nombre o razón social (fiscal)")
    nombre_comercial = models.CharField(max_length=255, blank=True, verbose_name="Nombre comercial")
    regimen_fiscal = models.ForeignKey(
        "fiscal.RegimenFiscal",
        on_delete=models.PROTECT,
        related_name="empresas",
        verbose_name="Régimen fiscal",
    )
    codigo_postal = models.CharField(max_length=5, verbose_name="Código postal (lugar de expedición)")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    serie_default = models.CharField(max_length=10, default="A", verbose_name="Serie de factura")
    siguiente_folio = models.PositiveIntegerField(default=1, verbose_name="Siguiente folio a asignar")

    class Meta:
        verbose_name = "Datos de la empresa"
        verbose_name_plural = "Datos de la empresa"

    def __str__(self):
        return f"{self.nombre_comercial or self.nombre_fiscal} ({self.rfc})"

    def get_folio_prefix(self):
        return "EMP"

    def get_slug_source(self):
        return self.nombre_fiscal

    @property
    def display_name(self):
        return (self.nombre_comercial or self.nombre_fiscal).strip()

    def clean(self):
        super().clean()
        if self.rfc:
            self.rfc = self.rfc.upper().strip()
            if not self.tipo_persona:
                raise ValidationError({"tipo_persona": "Indica el tipo de persona para validar el RFC."})
            longitud_esperada = 13 if self.tipo_persona == self.TipoPersona.FISICA else 12
            if len(self.rfc) != longitud_esperada:
                raise ValidationError({
                    "rfc": f"El RFC debe tener {longitud_esperada} caracteres para {self.get_tipo_persona_display()}.",
                })
            if not RFC_PATTERN.match(self.rfc):
                raise ValidationError({"rfc": "El formato del RFC no es válido."})

        if self.regimen_fiscal_id:
            if self.tipo_persona == self.TipoPersona.FISICA and not self.regimen_fiscal.aplica_fisica:
                raise ValidationError({"regimen_fiscal": "Este régimen fiscal no aplica para personas físicas."})
            if self.tipo_persona == self.TipoPersona.MORAL and not self.regimen_fiscal.aplica_moral:
                raise ValidationError({"regimen_fiscal": "Este régimen fiscal no aplica para personas morales."})

        if not self.pk and Empresa.objects.exists():
            raise ValidationError("Ya existen datos de la empresa registrados; edítalos en vez de crear otros.")

    def tomar_siguiente_folio(self):
        """Toma el folio con la fila de Empresa bloqueada, leída de nuevo de
        la base: dos facturas generadas al mismo tiempo nunca reciben el
        mismo folio (B17 en docs/AUDITORIA.md). Llamado dentro de la
        transacción que crea la factura, el bloqueo dura hasta que esta se
        confirma; si se revierte, el folio regresa con ella."""
        with transaction.atomic():
            empresa = Empresa.objects.select_for_update().get(pk=self.pk)
            folio = empresa.siguiente_folio
            empresa.siguiente_folio = folio + 1
            empresa.save(update_fields=["siguiente_folio", "updated_at", "updated_by"])
        self.siguiente_folio = folio + 1
        return folio


class SerieFolioMixin:
    """Serie-folio con que se muestra un comprobante (Factura o
    FacturaGlobal). Facturama asigna su propia serie y folio al timbrar
    -según el perfil fiscal de la cuenta- y se guardan aparte
    (serie_facturama/folio_facturama), sin tocar la serie/numero_folio
    internos: así nunca chocan con el folio interno de otro comprobante."""

    @property
    def serie_folio(self):
        if self.folio_facturama:
            return f"{self.serie_facturama}-{self.folio_facturama}" if self.serie_facturama else self.folio_facturama
        return f"{self.serie}-{self.numero_folio}"


def _campo_serie_facturama():
    return models.CharField(max_length=25, blank=True, verbose_name="Serie asignada por Facturama")


def _campo_folio_facturama():
    return models.CharField(max_length=40, blank=True, verbose_name="Folio asignado por Facturama")


class Factura(SerieFolioMixin, BaseAbstractModel):
    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        # Se mandó a Facturama y todavía no hay confirmación -o no llegó
        # (ver FacturamaError.incierto)-: no se puede volver a timbrar hasta
        # que alguien verifique en Facturama y la libere (ver
        # factura_service.liberar_timbrado), para no emitir un CFDI doble.
        TIMBRANDO = "timbrando", "Timbrando"
        TIMBRADA = "timbrada", "Timbrada"
        CANCELADA = "cancelada", "Cancelada"
        ERROR = "error", "Error al timbrar"

    venta = models.OneToOneField(
        "ventas.Venta",
        on_delete=models.PROTECT,
        related_name="factura",
        verbose_name="Venta",
    )
    serie = models.CharField(max_length=10, verbose_name="Serie")
    numero_folio = models.PositiveIntegerField(verbose_name="Folio")
    uso_cfdi = models.ForeignKey(
        "fiscal.UsoCFDI",
        on_delete=models.PROTECT,
        related_name="facturas",
        verbose_name="Uso de CFDI",
    )
    metodo_pago = models.ForeignKey(
        "fiscal.MetodoPago",
        on_delete=models.PROTECT,
        related_name="facturas",
        verbose_name="Método de pago",
    )
    moneda = models.CharField(max_length=3, default="MXN", verbose_name="Moneda")
    lugar_expedicion = models.CharField(max_length=5, verbose_name="Lugar de expedición (código postal)")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    facturama_id = models.CharField(max_length=100, blank=True, verbose_name="Id en Facturama")
    uuid_fiscal = models.CharField(max_length=36, blank=True, verbose_name="Folio fiscal (UUID)")
    serie_facturama = _campo_serie_facturama()
    folio_facturama = _campo_folio_facturama()
    fecha_timbrado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de timbrado")
    mensaje_error = models.TextField(blank=True, verbose_name="Mensaje de error")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["serie", "numero_folio"], name="unica_serie_folio"),
        ]
        indexes = [
            models.Index(fields=["estatus"]),
            models.Index(fields=["uuid_fiscal"]),
        ]

    def __str__(self):
        return f"{self.serie_folio} · {self.venta.cliente.display_name}"

    def get_folio_prefix(self):
        return "FAC"

    def get_slug_source(self):
        return f"{self.serie}-{self.numero_folio}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def total(self):
        return self.venta.total

    def clean(self):
        super().clean()
        if not self.venta_id:
            return

        cliente = self.venta.cliente
        if not cliente.facturable:
            raise ValidationError(
                "El cliente de esta venta no tiene datos fiscales completos "
                "(RFC, nombre fiscal, régimen fiscal)."
            )

        productos_sin_clave = [
            d.producto.nombre
            for d in self.venta.detalles.select_related("producto")
            if not d.producto.clave_prod_serv_sat_id or not d.producto.clave_unidad_sat_id
        ]
        if productos_sin_clave:
            raise ValidationError(
                "Estos productos no tienen clave SAT asignada (producto/servicio y/o unidad): "
                + ", ".join(productos_sin_clave)
            )


class FacturaGlobal(SerieFolioMixin, BaseAbstractModel):
    """Cierre fiscal del día: un solo CFDI que concentra las ventas a
    "Público en general" (sin RFC propio) de UN turno de cobro, para el
    receptor genérico que exige el SAT (ver RFC_PUBLICO_GENERAL en
    factura_service.py). Es distinta de `Factura` -esa es 1 a 1 con una
    Venta de un cliente identificado que sí pidió su factura- porque aquí
    se agrupan varias ventas en un solo comprobante.

    Se liga a `Turno`, no a una fecha/sucursal sueltas: hoy en la
    práctica un turno de caja ya equivale a "el día" de esa sucursal (una
    sola caja por sucursal), así que un turno = un periodo "Diario" ante
    el SAT. Si algún día una misma caja llega a abrir más de un turno el
    mismo día, dos facturas globales "Diario" el mismo día pueden no ser
    correctas fiscalmente -está documentado como pendiente de confirmar
    con el contador, no es una limitación técnica de este modelo."""

    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        TIMBRANDO = "timbrando", "Timbrando"  # ver Factura.Estatus.TIMBRANDO
        TIMBRADA = "timbrada", "Timbrada"
        CANCELADA = "cancelada", "Cancelada"
        ERROR = "error", "Error al timbrar"

    turno = models.OneToOneField(
        "products.Turno",
        on_delete=models.PROTECT,
        related_name="factura_global",
        verbose_name="Turno",
        help_text="Un turno solo puede tener una factura global.",
    )
    serie = models.CharField(max_length=10, verbose_name="Serie")
    numero_folio = models.PositiveIntegerField(verbose_name="Folio")
    metodo_pago = models.ForeignKey(
        "fiscal.MetodoPago",
        on_delete=models.PROTECT,
        related_name="facturas_globales",
        verbose_name="Método de pago",
    )
    forma_pago = models.ForeignKey(
        "fiscal.FormaPago",
        on_delete=models.PROTECT,
        related_name="facturas_globales",
        verbose_name="Forma de pago",
        help_text="La forma de pago que acumuló el monto más alto entre las ventas concentradas "
        "aquí (mismo criterio que el sistema anterior); el SAT no admite \"99 Por definir\" "
        "combinado con método de pago PUE (pago ya recibido, nunca diferido).",
    )
    moneda = models.CharField(max_length=3, default="MXN", verbose_name="Moneda")
    lugar_expedicion = models.CharField(max_length=5, verbose_name="Lugar de expedición (código postal)")
    periodo_mes = models.CharField(max_length=2, verbose_name="Mes del periodo (SAT)")
    periodo_anio = models.PositiveIntegerField(verbose_name="Año del periodo (SAT)")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    facturama_id = models.CharField(max_length=100, blank=True, verbose_name="Id en Facturama")
    uuid_fiscal = models.CharField(max_length=36, blank=True, verbose_name="Folio fiscal (UUID)")
    serie_facturama = _campo_serie_facturama()
    folio_facturama = _campo_folio_facturama()
    fecha_timbrado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de timbrado")
    mensaje_error = models.TextField(blank=True, verbose_name="Mensaje de error")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Factura global"
        verbose_name_plural = "Facturas globales"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["serie", "numero_folio"], name="unica_serie_folio_global"),
        ]
        indexes = [
            models.Index(fields=["estatus"]),
            models.Index(fields=["uuid_fiscal"]),
        ]

    def __str__(self):
        return f"{self.serie_folio} · Global {self.turno.folio}"

    def get_folio_prefix(self):
        return "FGL"

    def get_slug_source(self):
        return f"{self.serie}-{self.numero_folio}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def total(self):
        return sum((v.total for v in self.ventas.all()), Decimal("0.00"))
