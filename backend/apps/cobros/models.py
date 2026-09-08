from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class CuentaPorCobrar(BaseAbstractModel):
    """Espejo de pagos.CuentaPorPagar, del lado del cliente: se genera
    automáticamente cuando una Venta se registra con forma de pago "99 -
    Por definir" (la clave SAT de una venta a crédito, método de pago PPD,
    ver ventas.services.validar_venta_a_credito), nunca a mano."""

    class Estatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Cobro parcial"
        COBRADA = "cobrada", "Cobrada"
        CANCELADA = "cancelada", "Cancelada"

    venta = models.OneToOneField(
        "ventas.Venta",
        on_delete=models.PROTECT,
        related_name="cuenta_por_cobrar",
        verbose_name="Venta",
    )
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto total")
    fecha_emision = models.DateField(verbose_name="Fecha de emisión")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de vencimiento")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.PENDIENTE,
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Cuenta por cobrar"
        verbose_name_plural = "Cuentas por cobrar"
        ordering = ["fecha_vencimiento"]
        constraints = [
            models.CheckConstraint(condition=models.Q(monto_total__gt=0), name="cxc_monto_total_positivo"),
        ]
        indexes = [
            models.Index(fields=["estatus"]),
            models.Index(fields=["fecha_vencimiento"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.cliente.display_name}"

    def get_folio_prefix(self):
        return "CXC"

    def get_slug_source(self):
        return f"{self.folio}-{self.venta_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def cliente(self):
        return self.venta.cliente

    @property
    def total_cobrado(self):
        return sum((c.monto_cobrado for c in self.cobros.all() if c.is_active), Decimal("0.00"))

    @property
    def saldo_pendiente(self):
        return self.monto_total - self.total_cobrado

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
            self.estatus = self.Estatus.COBRADA
        elif self.total_cobrado > 0:
            self.estatus = self.Estatus.PARCIAL
        else:
            self.estatus = self.Estatus.PENDIENTE
        self.save(update_fields=["estatus", "updated_at", "updated_by"])

    def clean(self):
        super().clean()
        if self.monto_total is not None and self.monto_total <= 0:
            raise ValidationError({"monto_total": "El monto total debe ser mayor a cero."})
        if (
            self.fecha_vencimiento
            and self.fecha_emision
            and self.fecha_vencimiento < self.fecha_emision
        ):
            raise ValidationError({"fecha_vencimiento": "La fecha de vencimiento no puede ser anterior a la de emisión."})


class Cobro(BaseAbstractModel):
    """Espejo de pagos.Pago, del lado del cliente. A diferencia de Pago,
    aquí is_active siempre nace en True: el caso de "pago por nota de
    crédito pendiente de documento" no aplica igual del lado del cobro
    -una nota de crédito a favor del cliente normalmente sale de una
    devolución (ventas.DevolucionCliente), no de un Cobro-, así que ese
    campo queda disponible solo para un eventual borrado lógico manual,
    no con un default especial por forma de pago."""

    CLAVE_TRANSFERENCIA = "03"
    CLAVE_CHEQUE = "02"
    CLAVE_TARJETA_CREDITO = "04"
    CLAVE_TARJETA_DEBITO = "28"
    CLAVES_CON_BANCO = (CLAVE_TRANSFERENCIA, CLAVE_TARJETA_CREDITO, CLAVE_TARJETA_DEBITO)

    cuenta_por_cobrar = models.ForeignKey(
        CuentaPorCobrar,
        on_delete=models.CASCADE,
        related_name="cobros",
        verbose_name="Cuenta por cobrar",
    )
    fecha_cobro = models.DateField(verbose_name="Fecha de cobro")
    monto_cobrado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto cobrado")
    forma_pago = models.ForeignKey(
        "fiscal.FormaPago",
        on_delete=models.PROTECT,
        related_name="cobros_cliente",
        verbose_name="Forma de pago",
    )
    banco = models.ForeignKey(
        "pagos.Banco",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cobros",
        verbose_name="Banco",
        help_text="Requerido para transferencia; opcional para pago con tarjeta de crédito o débito.",
    )
    numero_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Número de cheque",
        help_text="Requerido cuando la forma de pago es cheque nominativo.",
    )
    comprobante = models.FileField(
        upload_to="cobros/comprobantes/",
        null=True,
        blank=True,
        verbose_name="Comprobante de cobro",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Cobro a cliente"
        verbose_name_plural = "Cobros a clientes"
        ordering = ["-fecha_cobro", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(monto_cobrado__gt=0), name="cobro_monto_cobrado_positivo"),
        ]
        indexes = [
            models.Index(fields=["cuenta_por_cobrar"]),
            models.Index(fields=["fecha_cobro"]),
        ]

    def __str__(self):
        return f"{self.folio} · ${self.monto_cobrado} de {self.cuenta_por_cobrar.cliente.display_name}"

    def get_folio_prefix(self):
        return "COB"

    def get_slug_source(self):
        return f"{self.folio}-{self.cuenta_por_cobrar_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.monto_cobrado is not None and self.monto_cobrado <= 0:
            raise ValidationError({"monto_cobrado": "El monto cobrado debe ser mayor a cero."})

        if self.forma_pago_id:
            clave = self.forma_pago.clave
            if clave == self.CLAVE_TRANSFERENCIA and not self.banco_id:
                raise ValidationError({"banco": "Indica el banco de la transferencia."})
            if clave not in self.CLAVES_CON_BANCO and self.banco_id:
                raise ValidationError({
                    "banco": "El banco solo aplica cuando la forma de pago es transferencia o pago con tarjeta.",
                })
            if clave == self.CLAVE_CHEQUE and not self.numero_referencia:
                raise ValidationError({"numero_referencia": "Indica el número de cheque."})
            if clave != self.CLAVE_CHEQUE and self.numero_referencia:
                raise ValidationError({
                    "numero_referencia": "Este número solo aplica para cheque nominativo.",
                })

        if not self.cuenta_por_cobrar_id:
            return

        cuenta = self.cuenta_por_cobrar
        saldo_antes = cuenta.saldo_pendiente
        if self.pk:
            cobro_previo = Cobro.objects.get(pk=self.pk)
            if cobro_previo.is_active:
                saldo_antes += cobro_previo.monto_cobrado

        if self.is_active and self.monto_cobrado > saldo_antes:
            raise ValidationError({
                "monto_cobrado": f"El monto excede el saldo pendiente (${saldo_antes}).",
            })
