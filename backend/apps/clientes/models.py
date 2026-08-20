from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel
from apps.core.validators import RFC_PATTERN


class Cliente(BaseAbstractModel):
    class TipoPersona(models.TextChoices):
        FISICA = "fisica", "Persona física"
        MORAL = "moral", "Persona moral"

    nombre = models.CharField(max_length=200, verbose_name="Nombre del cliente")
    tipo_persona = models.CharField(
        max_length=10,
        choices=TipoPersona.choices,
        blank=True,
        verbose_name="Tipo de persona",
    )
    rfc = models.CharField(
        max_length=13,
        unique=True,
        null=True,
        blank=True,
        verbose_name="RFC",
        error_messages={"unique": "Ya existe un %(model_name)s con este RFC."},
    )
    nombre_fiscal = models.CharField(max_length=255, blank=True, verbose_name="Nombre o razón social (fiscal)")
    regimen_fiscal = models.ForeignKey(
        "fiscal.RegimenFiscal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clientes",
        verbose_name="Régimen fiscal",
    )
    uso_cfdi = models.ForeignKey(
        "fiscal.UsoCFDI",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="clientes",
        verbose_name="Uso de CFDI",
    )
    codigo_postal = models.CharField(max_length=5, blank=True, verbose_name="Código postal fiscal")
    contacto_telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    contacto_email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    # Crédito que la veterinaria le otorga a este cliente (cuentas por cobrar),
    # no confundir con el crédito que otorgan los proveedores (apps.proveedores.Proveedor).
    tiene_credito = models.BooleanField(default=False, verbose_name="Crédito autorizado")
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Límite de crédito")
    dias_credito = models.PositiveIntegerField(default=0, verbose_name="Días de crédito")
    lista_precio = models.ForeignKey(
        "products.ListaPrecio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes",
        verbose_name="Lista de precios",
        help_text="Lista de precios que se aplica por defecto a este cliente en ventas y cotizaciones.",
    )
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Descuento (%)")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                name="cliente_descuento_rango_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(limite_credito__gte=0),
                name="cliente_limite_credito_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["nombre"]),
            models.Index(fields=["rfc"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.rfc})" if self.rfc else self.nombre

    def get_folio_prefix(self):
        return "CLI"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

    @property
    def facturable(self):
        return bool(self.rfc and self.nombre_fiscal and self.regimen_fiscal_id and self.uso_cfdi_id)

    def clean(self):
        super().clean()

        # RFC vacío se normaliza a None (no "") para que la unicidad no choque
        # entre varios clientes "público en general" sin RFC.
        self.rfc = (self.rfc or "").upper().strip() or None

        campos_fiscales = [self.rfc, self.nombre_fiscal, self.regimen_fiscal_id, self.uso_cfdi_id, self.codigo_postal]
        if any(campos_fiscales) and not all(campos_fiscales):
            raise ValidationError(
                "Para poder facturarle a este cliente se necesitan todos los datos fiscales: "
                "RFC, nombre fiscal, régimen fiscal, uso de CFDI y código postal."
            )

        if self.rfc:
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

        if self.uso_cfdi_id:
            if self.tipo_persona == self.TipoPersona.FISICA and not self.uso_cfdi.aplica_fisica:
                raise ValidationError({"uso_cfdi": "Este uso de CFDI no aplica para personas físicas."})
            if self.tipo_persona == self.TipoPersona.MORAL and not self.uso_cfdi.aplica_moral:
                raise ValidationError({"uso_cfdi": "Este uso de CFDI no aplica para personas morales."})

        if not self.tiene_credito and (self.limite_credito or self.dias_credito):
            raise ValidationError({
                "tiene_credito": "Activa el crédito autorizado antes de definir límite o días de crédito.",
            })

        if self.descuento < 0 or self.descuento > 100:
            raise ValidationError({"descuento": "El descuento debe estar entre 0 y 100."})

        if self.limite_credito < 0:
            raise ValidationError({"limite_credito": "El límite de crédito no puede ser negativo."})
