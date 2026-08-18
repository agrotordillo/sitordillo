from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.models import BaseAbstractModel


class Venta(BaseAbstractModel):
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="ventas",
        verbose_name="Cliente",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="ventas",
        verbose_name="Sucursal",
    )
    forma_pago = models.ForeignKey(
        "fiscal.FormaPago",
        on_delete=models.PROTECT,
        related_name="ventas",
        verbose_name="Forma de pago",
    )
    fecha_venta = models.DateTimeField(default=timezone.now, verbose_name="Fecha de venta")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha_venta"]
        indexes = [
            models.Index(fields=["cliente"]),
            models.Index(fields=["almacen"]),
            models.Index(fields=["fecha_venta"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.cliente.display_name}"

    def get_folio_prefix(self):
        return "VTA"

    def get_slug_source(self):
        return f"{self.folio}-{self.cliente_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def subtotal(self):
        return sum((detalle.subtotal for detalle in self.detalles.all()), Decimal("0.00"))

    @property
    def total(self):
        # Sin desglose de impuestos por ahora: se incorpora en la fase de Facturación.
        return self.subtotal

    def clean(self):
        super().clean()
        if self.almacen_id and self.almacen.tipo != self.almacen.Tipo.SUCURSAL:
            raise ValidationError({"almacen": "Las ventas se registran desde una sucursal, no desde el CEDIS."})


class VentaDetalle(BaseAbstractModel):
    class Estrategia(models.TextChoices):
        FIFO = "fifo", "FIFO (primero en entrar, primero en salir)"
        FEFO = "fefo", "FEFO (primero en caducar, primero en salir)"

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Venta",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_venta",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio unitario")
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Descuento (%)")
    estrategia_salida = models.CharField(
        max_length=10,
        choices=Estrategia.choices,
        default=Estrategia.FIFO,
        verbose_name="Estrategia de salida",
    )

    class Meta:
        verbose_name = "Detalle de venta"
        verbose_name_plural = "Detalles de venta"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="vtd_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="vtd_precio_unitario_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                name="vtd_descuento_rango_valido",
            ),
        ]
        indexes = [
            models.Index(fields=["venta"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "VTD"

    def get_slug_source(self):
        return f"{self.venta_id}-{self.producto_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def subtotal(self):
        bruto = (self.cantidad or Decimal("0")) * (self.precio_unitario or Decimal("0"))
        return bruto * (Decimal("1") - (self.descuento or Decimal("0")) / Decimal("100"))

    @property
    def cantidad_devuelta(self):
        return sum(
            (d.cantidad for d in self.devoluciones.all()),
            Decimal("0.00"),
        )

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})
        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError({"precio_unitario": "El precio unitario no puede ser negativo."})
        if self.descuento is not None and (self.descuento < 0 or self.descuento > 100):
            raise ValidationError({"descuento": "El descuento debe estar entre 0 y 100."})


class VentaDetalleLote(BaseAbstractModel):
    """Registra de qué lote(s) salió cada línea de venta (vía FIFO/FEFO), con
    el costo de ese momento. Es lo que permite calcular un costo justo al
    reingresar mercancía por una devolución."""

    detalle = models.ForeignKey(
        VentaDetalle,
        on_delete=models.CASCADE,
        related_name="lotes",
        verbose_name="Detalle de venta",
    )
    lote = models.ForeignKey(
        "inventario.Lote",
        on_delete=models.PROTECT,
        related_name="ventas",
        verbose_name="Lote de origen",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad tomada")
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Costo unitario al momento de la venta")

    class Meta:
        verbose_name = "Lote de venta"
        verbose_name_plural = "Lotes de venta"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="vtl_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["detalle"]),
            models.Index(fields=["lote"]),
        ]

    def __str__(self):
        return f"{self.lote} → {self.cantidad}"

    def get_folio_prefix(self):
        return "VTL"

    def get_slug_source(self):
        return f"{self.detalle_id}-{self.lote_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()


class DevolucionCliente(BaseAbstractModel):
    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        related_name="devoluciones",
        verbose_name="Venta original",
    )
    fecha = models.DateField(verbose_name="Fecha de devolución")
    motivo = models.TextField(blank=True, verbose_name="Motivo")

    class Meta:
        verbose_name = "Devolución de cliente"
        verbose_name_plural = "Devoluciones de cliente"
        ordering = ["-fecha", "-created_at"]
        indexes = [
            models.Index(fields=["venta"]),
        ]

    def __str__(self):
        return f"{self.folio} · devolución de {self.venta.folio}"

    def get_folio_prefix(self):
        return "DEV"

    def get_slug_source(self):
        return f"{self.folio}-{self.venta_id}"

    @property
    def display_name(self):
        return self.__str__()


class DevolucionClienteDetalle(BaseAbstractModel):
    devolucion = models.ForeignKey(
        DevolucionCliente,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Devolución",
    )
    venta_detalle = models.ForeignKey(
        VentaDetalle,
        on_delete=models.PROTECT,
        related_name="devoluciones",
        verbose_name="Línea de venta original",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad devuelta")
    reingresa_a_inventario = models.BooleanField(
        default=True,
        verbose_name="Reingresa a inventario",
        help_text="Si no aplica, el producto se da de baja como merma en lugar de regresar a stock.",
    )

    class Meta:
        verbose_name = "Detalle de devolución"
        verbose_name_plural = "Detalles de devolución"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="dvd_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["devolucion"]),
            models.Index(fields=["venta_detalle"]),
        ]

    def __str__(self):
        return f"{self.venta_detalle.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "DVD"

    def get_slug_source(self):
        return f"{self.devolucion_id}-{self.venta_detalle_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad devuelta debe ser mayor a cero."})
        if self.venta_detalle_id and self.cantidad is not None:
            ya_devuelto = self.venta_detalle.cantidad_devuelta
            if self.pk:
                ya_devuelto -= type(self).objects.get(pk=self.pk).cantidad
            pendiente = self.venta_detalle.cantidad - ya_devuelto
            if self.cantidad > pendiente:
                raise ValidationError({
                    "cantidad": f"No puede devolver más de lo pendiente para esta línea ({pendiente}).",
                })
