from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel
from apps.core.validators import RFC_PATTERN


class Proveedor(BaseAbstractModel):
    class TipoPersona(models.TextChoices):
        FISICA = "fisica", "Persona física"
        MORAL = "moral", "Persona moral"

    tipo_persona = models.CharField(
        max_length=10,
        choices=TipoPersona.choices,
        verbose_name="Tipo de persona",
    )
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
        related_name="proveedores",
        verbose_name="Régimen fiscal",
    )
    tiene_credito = models.BooleanField(default=False, verbose_name="Crédito autorizado")
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Límite de crédito")
    dias_credito = models.PositiveIntegerField(default=0, verbose_name="Días de crédito")
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Descuento (%)")
    descuento_pronto_pago = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Descuento por pronto pago (%)",
    )
    dias_pronto_pago = models.PositiveIntegerField(
        default=0,
        verbose_name="Días para pronto pago",
        help_text="Si el pago se hace dentro de estos días desde la orden, aplica el descuento por pronto pago.",
    )
    contacto_nombre = models.CharField(max_length=150, blank=True, verbose_name="Nombre de contacto")
    contacto_telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono de contacto")
    contacto_email = models.EmailField(blank=True, verbose_name="Correo de contacto")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["nombre_fiscal"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                name="proveedor_descuento_rango_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(descuento_pronto_pago__gte=0) & models.Q(descuento_pronto_pago__lte=100),
                name="proveedor_descuento_pronto_pago_rango_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(limite_credito__gte=0),
                name="proveedor_limite_credito_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["rfc"]),
            models.Index(fields=["nombre_fiscal"]),
            models.Index(fields=["regimen_fiscal"]),
        ]

    def __str__(self):
        return f"{self.nombre_comercial or self.nombre_fiscal} ({self.rfc})"

    def get_folio_prefix(self):
        return "PRV"

    def get_slug_source(self):
        return self.nombre_comercial or self.nombre_fiscal

    @property
    def display_name(self):
        return (self.nombre_comercial or self.nombre_fiscal).strip()

    @property
    def nombre(self):
        # Compatibilidad con OptionSerializer (source="nombre") usado en selects rápidos.
        return self.display_name

    def clean(self):
        super().clean()
        if self.rfc:
            self.rfc = self.rfc.upper().strip()

        if self.tipo_persona and self.rfc:
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

        if not self.tiene_credito and (self.limite_credito or self.dias_credito):
            raise ValidationError({
                "tiene_credito": "Activa el crédito autorizado antes de definir límite o días de crédito.",
            })

        if not self.tiene_credito and (self.descuento_pronto_pago or self.dias_pronto_pago):
            raise ValidationError({
                "tiene_credito": "El pronto pago solo aplica a proveedores con crédito autorizado.",
            })

        if bool(self.descuento_pronto_pago) != bool(self.dias_pronto_pago):
            raise ValidationError({
                "dias_pronto_pago": "El descuento y los días de pronto pago deben capturarse juntos, o dejarse ambos en cero.",
            })

        if self.dias_pronto_pago and self.dias_credito and self.dias_pronto_pago > self.dias_credito:
            raise ValidationError({
                "dias_pronto_pago": "Los días de pronto pago no pueden ser mayores a los días de crédito.",
            })

        if self.descuento < 0 or self.descuento > 100:
            raise ValidationError({"descuento": "El descuento debe estar entre 0 y 100."})

        if self.descuento_pronto_pago < 0 or self.descuento_pronto_pago > 100:
            raise ValidationError({"descuento_pronto_pago": "El descuento por pronto pago debe estar entre 0 y 100."})

        if self.limite_credito < 0:
            raise ValidationError({"limite_credito": "El límite de crédito no puede ser negativo."})
