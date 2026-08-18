from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
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
        folio = self.siguiente_folio
        self.siguiente_folio += 1
        self.save(update_fields=["siguiente_folio", "updated_at", "updated_by"])
        return folio


class Factura(BaseAbstractModel):
    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
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
        return f"{self.serie}-{self.numero_folio} · {self.venta.cliente.display_name}"

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
                "(RFC, nombre fiscal, régimen fiscal, uso de CFDI, código postal)."
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
