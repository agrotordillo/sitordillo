from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class Banco(BaseAbstractModel):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del banco",
        error_messages={"unique": "Ya existe un %(model_name)s con este nombre."},
    )

    class Meta:
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "BAN"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class CuentaPorPagar(BaseAbstractModel):
    class Estatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Pago parcial"
        PAGADA = "pagada", "Pagada"
        CANCELADA = "cancelada", "Cancelada"

    orden_compra = models.OneToOneField(
        "compras.OrdenCompra",
        on_delete=models.PROTECT,
        related_name="cuenta_por_pagar",
        verbose_name="Orden de compra",
    )
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto total")
    fecha_emision = models.DateField(verbose_name="Fecha de emisión")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de vencimiento")
    fecha_limite_pronto_pago = models.DateField(
        null=True, blank=True, verbose_name="Fecha límite para pronto pago"
    )
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.PENDIENTE,
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Cuenta por pagar"
        verbose_name_plural = "Cuentas por pagar"
        ordering = ["fecha_vencimiento"]
        constraints = [
            models.CheckConstraint(condition=models.Q(monto_total__gt=0), name="cxp_monto_total_positivo"),
        ]
        indexes = [
            models.Index(fields=["estatus"]),
            models.Index(fields=["fecha_vencimiento"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.orden_compra.proveedor.display_name}"

    def get_folio_prefix(self):
        return "CXP"

    def get_slug_source(self):
        return f"{self.folio}-{self.orden_compra_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def proveedor(self):
        return self.orden_compra.proveedor

    @property
    def total_pagado(self):
        # Un pago Inactivo (is_active=False) todavía no liquida realmente
        # el adeudo -típicamente porque es por compensación/nota de crédito
        # y ese documento aún no existe, ver Pago.clean()- así que no
        # cuenta aquí hasta que se marque Activo.
        return sum((p.monto_pagado for p in self.pagos.all() if p.is_active), Decimal("0.00"))

    @property
    def total_descuento(self):
        return sum((p.monto_descuento for p in self.pagos.all() if p.is_active), Decimal("0.00"))

    @property
    def saldo_pendiente(self):
        return self.monto_total - self.total_pagado - self.total_descuento

    @property
    def esta_vencida(self):
        from django.utils import timezone
        return (
            self.estatus in (self.Estatus.PENDIENTE, self.Estatus.PARCIAL)
            and self.fecha_vencimiento < timezone.localdate()
        )

    def actualizar_estatus(self):
        if self.estatus == self.Estatus.CANCELADA:
            return
        saldo = self.saldo_pendiente
        if saldo <= 0:
            self.estatus = self.Estatus.PAGADA
        elif self.total_pagado > 0 or self.total_descuento > 0:
            self.estatus = self.Estatus.PARCIAL
        else:
            self.estatus = self.Estatus.PENDIENTE
        self.save(update_fields=["estatus", "updated_at", "updated_by"])

    def clean(self):
        super().clean()
        if self.orden_compra_id and self.orden_compra.estatus not in (
            self.orden_compra.Estatus.PARCIAL,
            self.orden_compra.Estatus.RECIBIDA,
        ):
            raise ValidationError({
                "orden_compra": "Solo se puede generar una cuenta por pagar de una orden ya recibida (parcial o completa).",
            })
        if self.monto_total is not None and self.monto_total <= 0:
            raise ValidationError({"monto_total": "El monto total debe ser mayor a cero."})
        if (
            self.fecha_vencimiento
            and self.fecha_emision
            and self.fecha_vencimiento < self.fecha_emision
        ):
            raise ValidationError({"fecha_vencimiento": "La fecha de vencimiento no puede ser anterior a la de emisión."})


class Pago(BaseAbstractModel):
    # Claves del catálogo oficial SAT c_FormaPago (fiscal.FormaPago) que
    # requieren o admiten un dato adicional al registrar el pago.
    CLAVE_TRANSFERENCIA = "03"
    CLAVE_CHEQUE = "02"
    CLAVE_COMPENSACION = "17"  # "Nota de crédito" del proveedor en la operación del negocio.
    CLAVE_TARJETA_CREDITO = "04"
    CLAVE_TARJETA_DEBITO = "28"
    # El banco es obligatorio en transferencia y opcional (para reconciliar
    # el estado de cuenta) en pago con tarjeta.
    CLAVES_CON_BANCO = (CLAVE_TRANSFERENCIA, CLAVE_TARJETA_CREDITO, CLAVE_TARJETA_DEBITO)

    cuenta_por_pagar = models.ForeignKey(
        CuentaPorPagar,
        on_delete=models.CASCADE,
        related_name="pagos",
        verbose_name="Cuenta por pagar",
    )
    fecha_pago = models.DateField(verbose_name="Fecha de pago")
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto pagado")
    forma_pago = models.ForeignKey(
        "fiscal.FormaPago",
        on_delete=models.PROTECT,
        related_name="pagos_proveedor",
        verbose_name="Forma de pago",
    )
    banco = models.ForeignKey(
        Banco,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos",
        verbose_name="Banco",
        help_text="Requerido para transferencia; opcional para pago con tarjeta de crédito o débito.",
    )
    numero_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Número de cheque o nota de crédito",
        help_text="Requerido cuando la forma de pago es cheque nominativo o compensación (nota de crédito).",
    )
    comprobante = models.FileField(
        upload_to="pagos/comprobantes/",
        null=True,
        blank=True,
        verbose_name="Comprobante de pago",
    )
    aplica_descuento_pronto_pago = models.BooleanField(
        default=False, verbose_name="Aplica descuento por pronto pago"
    )
    monto_descuento = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Monto de descuento"
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Pago a proveedor"
        verbose_name_plural = "Pagos a proveedores"
        ordering = ["-fecha_pago", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(monto_pagado__gt=0), name="pago_monto_pagado_positivo"),
            models.CheckConstraint(condition=models.Q(monto_descuento__gte=0), name="pago_monto_descuento_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["cuenta_por_pagar"]),
            models.Index(fields=["fecha_pago"]),
        ]

    def __str__(self):
        return f"{self.folio} · ${self.monto_pagado} a {self.cuenta_por_pagar.proveedor.display_name}"

    def get_folio_prefix(self):
        return "PAG"

    def get_slug_source(self):
        return f"{self.folio}-{self.cuenta_por_pagar_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.monto_pagado is not None and self.monto_pagado <= 0:
            raise ValidationError({"monto_pagado": "El monto pagado debe ser mayor a cero."})

        if self.forma_pago_id:
            clave = self.forma_pago.clave
            if not self.pk and clave == self.CLAVE_COMPENSACION:
                # Un pago por compensación (nota de crédito) se registra
                # Inactivo por default: el adeudo no queda realmente
                # liquidado hasta que exista el documento de la nota de
                # crédito. El usuario lo marca Activo cuando ya se elaboró
                # (ver Pago.is_active / CuentaPorPagar.total_pagado, que
                # solo cuenta los pagos activos). Los demás medios de pago
                # mueven el dinero de inmediato, así que nacen Activos
                # (default de BaseAbstractModel).
                self.is_active = False
            if clave == self.CLAVE_TRANSFERENCIA and not self.banco_id:
                raise ValidationError({"banco": "Indica el banco de la transferencia."})
            if clave not in self.CLAVES_CON_BANCO and self.banco_id:
                raise ValidationError({
                    "banco": "El banco solo aplica cuando la forma de pago es transferencia o pago con tarjeta.",
                })
            if clave in (self.CLAVE_CHEQUE, self.CLAVE_COMPENSACION) and not self.numero_referencia:
                etiqueta = "cheque" if clave == self.CLAVE_CHEQUE else "nota de crédito"
                raise ValidationError({"numero_referencia": f"Indica el número de {etiqueta}."})
            if clave not in (self.CLAVE_CHEQUE, self.CLAVE_COMPENSACION) and self.numero_referencia:
                raise ValidationError({
                    "numero_referencia": "Este número solo aplica para cheque nominativo o compensación (nota de crédito).",
                })

        if not self.cuenta_por_pagar_id:
            return

        cuenta = self.cuenta_por_pagar
        saldo_antes = cuenta.saldo_pendiente
        if self.pk:
            pago_previo = Pago.objects.get(pk=self.pk)
            saldo_antes += pago_previo.monto_pagado + pago_previo.monto_descuento

        self.monto_descuento = Decimal("0.00")
        if self.aplica_descuento_pronto_pago:
            proveedor = cuenta.proveedor
            if not cuenta.fecha_limite_pronto_pago:
                raise ValidationError({
                    "aplica_descuento_pronto_pago": "Esta cuenta no tiene condición de pronto pago.",
                })
            if self.fecha_pago and self.fecha_pago > cuenta.fecha_limite_pronto_pago:
                raise ValidationError({
                    "aplica_descuento_pronto_pago": f"El plazo de pronto pago venció el {cuenta.fecha_limite_pronto_pago}.",
                })
            ya_aplicado = cuenta.pagos.filter(aplica_descuento_pronto_pago=True).exclude(pk=self.pk).exists()
            if ya_aplicado:
                raise ValidationError({
                    "aplica_descuento_pronto_pago": "Esta cuenta ya tiene un pago con descuento por pronto pago aplicado.",
                })
            self.monto_descuento = (cuenta.monto_total * proveedor.descuento_pronto_pago / Decimal("100")).quantize(
                Decimal("0.01")
            )

        if self.monto_pagado + self.monto_descuento > saldo_antes:
            raise ValidationError({
                "monto_pagado": f"El monto excede el saldo pendiente (${saldo_antes}).",
            })
