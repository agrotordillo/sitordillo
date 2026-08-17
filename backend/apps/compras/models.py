from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class OrdenCompra(BaseAbstractModel):
    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADA = "enviada", "Enviada"
        PARCIAL = "parcial", "Recepción parcial"
        RECIBIDA = "recibida", "Recibida"
        CANCELADA = "cancelada", "Cancelada"

    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        related_name="ordenes_compra",
        verbose_name="Proveedor",
    )
    fecha_orden = models.DateField(verbose_name="Fecha de orden")
    fecha_entrega_estimada = models.DateField(null=True, blank=True, verbose_name="Fecha de entrega estimada")
    estatus = models.CharField(
        max_length=15,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Orden de compra"
        verbose_name_plural = "Órdenes de compra"
        ordering = ["-fecha_orden", "-created_at"]
        indexes = [
            models.Index(fields=["proveedor"]),
            models.Index(fields=["estatus"]),
            models.Index(fields=["fecha_orden"]),
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
        # Sin desglose de impuestos por ahora: se incorpora en la fase de Facturación.
        return self.subtotal

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

    class Meta:
        verbose_name = "Detalle de orden de compra"
        verbose_name_plural = "Detalles de orden de compra"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ocd_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="ocd_precio_unitario_no_negativo"),
            models.CheckConstraint(condition=models.Q(cantidad_recibida__gte=0), name="ocd_cantidad_recibida_no_negativa"),
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
    def subtotal(self):
        return (self.cantidad or Decimal("0")) * (self.precio_unitario or Decimal("0"))

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
