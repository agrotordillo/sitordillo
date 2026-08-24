from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class PromocionProveedor(BaseAbstractModel):
    class TipoDescuento(models.TextChoices):
        PORCENTAJE = "porcentaje", "% de descuento"
        PRECIO_FIJO = "precio_fijo", "Precio promocional fijo"

    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        related_name="promociones",
        verbose_name="Proveedor",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="promociones_proveedor",
        verbose_name="Producto",
    )
    tipo_descuento = models.CharField(
        max_length=15,
        choices=TipoDescuento.choices,
        verbose_name="Tipo de promoción",
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Descuento (%)"
    )
    precio_promocional = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Precio promocional"
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Promoción de proveedor"
        verbose_name_plural = "Promociones de proveedor"
        ordering = ["-fecha_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fecha_fin__gte=models.F("fecha_inicio")),
                name="promo_fecha_fin_no_anterior_inicio",
            ),
        ]
        indexes = [
            models.Index(fields=["proveedor", "producto"]),
            models.Index(fields=["fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} · {self.proveedor.display_name} ({self.fecha_inicio} a {self.fecha_fin})"

    def get_folio_prefix(self):
        return "PROMO"

    def get_slug_source(self):
        return f"{self.proveedor_id}-{self.producto_id}-{self.fecha_inicio}"

    @property
    def display_name(self):
        return self.__str__()

    def vigente_en(self, fecha):
        return self.fecha_inicio <= fecha <= self.fecha_fin

    def precio_para(self, precio_base):
        if self.tipo_descuento == self.TipoDescuento.PRECIO_FIJO:
            return self.precio_promocional
        precio_base = precio_base or Decimal("0")
        precio = precio_base * (Decimal("1") - self.descuento_porcentaje / Decimal("100"))
        return precio.quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin no puede ser anterior a la fecha de inicio."})

        if self.tipo_descuento == self.TipoDescuento.PORCENTAJE:
            if not self.descuento_porcentaje:
                raise ValidationError({"descuento_porcentaje": "Indica el porcentaje de descuento."})
            if self.descuento_porcentaje <= 0 or self.descuento_porcentaje > 100:
                raise ValidationError({"descuento_porcentaje": "El descuento debe estar entre 0 y 100."})
            self.precio_promocional = None
        elif self.tipo_descuento == self.TipoDescuento.PRECIO_FIJO:
            if not self.precio_promocional or self.precio_promocional <= 0:
                raise ValidationError({"precio_promocional": "Indica el precio promocional."})
            self.descuento_porcentaje = None

        if self.proveedor_id and self.producto_id and self.fecha_inicio and self.fecha_fin:
            traslape = PromocionProveedor.objects.filter(
                proveedor_id=self.proveedor_id,
                producto_id=self.producto_id,
                fecha_inicio__lte=self.fecha_fin,
                fecha_fin__gte=self.fecha_inicio,
            ).exclude(pk=self.pk)
            if traslape.exists():
                raise ValidationError(
                    "Ya existe una promoción de este producto con este proveedor que se traslapa en fechas."
                )


class OrdenCompra(BaseAbstractModel):
    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADA = "enviada", "Enviada"
        PARCIAL = "parcial", "Recepción parcial"
        RECIBIDA = "recibida", "Recibida"
        CANCELADA = "cancelada", "Cancelada"

    class EstadoPago(models.TextChoices):
        CONTADO = "contado", "Contado"
        CREDITO = "credito", "Crédito"

    class MedioPago(models.TextChoices):
        CAJA = "caja", "Caja"
        BANCO = "banco", "Banco"
        INDEFINIDO = "indefinido", "Indefinido"

    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
        verbose_name="Proveedor",
    )
    almacen_destino = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="ordenes_compra_destino",
        null=True,
        blank=True,
        verbose_name="Almacén destino",
        help_text=(
            "El alta de la compra siempre queda a nombre del CEDIS (ahí está la "
            "relación comercial con el proveedor); este campo indica dónde debe "
            "impactar físicamente la mercancía: el propio CEDIS, o una sucursal "
            "cuando el proveedor entrega directo ahí."
        ),
    )
    fecha_orden = models.DateField(verbose_name="Fecha de orden")
    fecha_entrega_estimada = models.DateField(null=True, blank=True, verbose_name="Fecha de entrega estimada")
    estatus = models.CharField(
        max_length=15,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    es_fiscal = models.BooleanField(default=False, verbose_name="Es fiscal")
    documento = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Documento",
        help_text="Número de factura o folio de nota de venta del proveedor.",
    )
    estado_pago = models.CharField(
        max_length=10,
        choices=EstadoPago.choices,
        default=EstadoPago.CONTADO,
        verbose_name="Estado de pago",
    )
    medio_pago = models.CharField(
        max_length=15,
        choices=MedioPago.choices,
        default=MedioPago.INDEFINIDO,
        verbose_name="Medio de pago",
    )
    forma_pago = models.ForeignKey(
        "fiscal.FormaPago",
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
        null=True,
        blank=True,
        verbose_name="Método de pago",
    )
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="IVA")
    ieps = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="IEPS")
    retencion_iva = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Retención IVA"
    )
    retencion_isr = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Retención ISR"
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"
        ordering = ["-fecha_orden", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(iva__gte=0), name="oc_iva_no_negativo"),
            models.CheckConstraint(condition=models.Q(ieps__gte=0), name="oc_ieps_no_negativo"),
            models.CheckConstraint(condition=models.Q(retencion_iva__gte=0), name="oc_retencion_iva_no_negativa"),
            models.CheckConstraint(condition=models.Q(retencion_isr__gte=0), name="oc_retencion_isr_no_negativa"),
        ]
        indexes = [
            models.Index(fields=["proveedor"]),
            models.Index(fields=["estatus"]),
            models.Index(fields=["fecha_orden"]),
            models.Index(fields=["almacen_destino"]),
        ]

    def __str__(self):
        return f"{self.folio} - {self.proveedor.display_name}"

    def get_folio_prefix(self):
        return "OC"

    def get_slug_source(self):
        return f"{self.folio}-{self.proveedor.display_name}"

    @property
    def display_name(self):
        return self.folio

    @property
    def subtotal(self):
        return sum((detalle.subtotal for detalle in self.detalles.all()), Decimal("0.00"))

    @property
    def total(self):
        return self.subtotal + self.iva + self.ieps - self.retencion_iva - self.retencion_isr

    def clean(self):
        super().clean()
        if self.fecha_entrega_estimada and self.fecha_orden and self.fecha_entrega_estimada < self.fecha_orden:
            raise ValidationError({
                "fecha_entrega_estimada": "La fecha de entrega estimada no puede ser anterior a la fecha de la orden.",
            })


class OrdenCompraDetalle(BaseAbstractModel):
    orden_compra = models.ForeignKey(
        OrdenCompra,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Orden de compra",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_orden_compra",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio unitario")
    cantidad_recibida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Cantidad recibida",
    )
    cantidad_merma = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Cantidad dañada (no facturable)",
        help_text=(
            "De lo recibido, cuánto se dio de baja por llegar en mal estado. El "
            "proveedor descuenta esta cantidad de lo que factura y cobra."
        ),
    )

    class Meta:
        verbose_name = "Detalle de orden de compra"
        verbose_name_plural = "Detalles de orden de compra"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ocd_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="ocd_precio_unitario_no_negativo"),
            models.CheckConstraint(condition=models.Q(cantidad_recibida__gte=0), name="ocd_cantidad_recibida_no_negativa"),
            models.CheckConstraint(condition=models.Q(cantidad_merma__gte=0), name="ocd_cantidad_merma_no_negativa"),
        ]
        indexes = [
            models.Index(fields=["orden_compra"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "OCD"

    def get_slug_source(self):
        return f"{self.orden_compra_id}-{self.producto_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def cantidad_facturable(self):
        """Cantidad sobre la que realmente se factura y se paga al proveedor.
        Antes de recibir nada, es la cantidad ordenada (mejor estimado). Una
        vez que empezó a recibirse, es lo recibido menos lo dado de baja por
        llegar dañado (cantidad_merma) — el proveedor descuenta esa merma de
        su factura, así que no se paga por ella."""
        if self.cantidad_recibida:
            return max(Decimal("0.00"), self.cantidad_recibida - (self.cantidad_merma or Decimal("0.00")))
        return self.cantidad or Decimal("0.00")

    @property
    def subtotal(self):
        bruto = self.cantidad_facturable * (self.precio_unitario or Decimal("0"))
        return bruto.quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})
        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError({"precio_unitario": "El precio unitario no puede ser negativo."})
        if (
            self.cantidad_recibida is not None
            and self.cantidad is not None
            and self.cantidad_recibida > self.cantidad
        ):
            raise ValidationError({
                "cantidad_recibida": "La cantidad recibida no puede ser mayor a la cantidad ordenada.",
            })
        if (
            self.cantidad_merma is not None
            and self.cantidad_recibida is not None
            and self.cantidad_merma > self.cantidad_recibida
        ):
            raise ValidationError({
                "cantidad_merma": "No puedes dar de baja más de lo que se recibió en esta línea.",
            })
