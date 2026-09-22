from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from apps.core.models import BaseAbstractModel


class Cotizacion(BaseAbstractModel):
    class Estatus(models.TextChoices):
        ABIERTA = "abierta", "Abierta"
        CONVERTIDA = "convertida", "Convertida a venta"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="cotizaciones",
        verbose_name="Cliente",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="cotizaciones",
        verbose_name="Sucursal",
    )
    punto_venta = models.ForeignKey(
        "products.PuntoVenta",
        on_delete=models.PROTECT,
        related_name="cotizaciones",
        verbose_name="Punto de venta",
    )
    numero_documento = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="Número de cotización",
        help_text="Folio para el cliente: número de almacén + número de punto de venta + consecutivo. Se genera solo al guardar y no se puede editar.",
    )
    fecha_cotizacion = models.DateTimeField(default=timezone.now, verbose_name="Fecha de cotización")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.ABIERTA,
        verbose_name="Estatus",
    )
    venta = models.OneToOneField(
        "ventas.Venta",
        on_delete=models.SET_NULL,
        related_name="cotizacion_origen",
        null=True,
        blank=True,
        verbose_name="Venta generada",
    )

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ["-fecha_cotizacion"]
        indexes = [
            models.Index(fields=["cliente"]),
            models.Index(fields=["almacen"]),
            models.Index(fields=["estatus"]),
            models.Index(fields=["punto_venta"], name="cotizaciones_punto_venta_idx"),
        ]

    def __str__(self):
        return f"{self.folio} · {self.cliente.display_name}"

    def get_folio_prefix(self):
        return "COT"

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
        return self.subtotal

    def clean(self):
        super().clean()
        if self.almacen_id and self.almacen.tipo != self.almacen.Tipo.SUCURSAL:
            raise ValidationError({"almacen": "Las cotizaciones se registran desde una sucursal, no desde el CEDIS."})
        if self.almacen_id and self.punto_venta_id and self.punto_venta.almacen_id != self.almacen_id:
            raise ValidationError({"punto_venta": "El punto de venta debe pertenecer a la sucursal seleccionada."})

    def save(self, *args, **kwargs):
        if not self.numero_documento and self.punto_venta_id:
            from apps.products.models import PuntoVenta

            with transaction.atomic():
                punto_venta = (
                    PuntoVenta.objects.select_for_update().select_related("almacen").get(pk=self.punto_venta_id)
                )
                self.numero_documento = punto_venta.tomar_siguiente_folio_cotizacion()
        super().save(*args, **kwargs)


class CotizacionDetalle(BaseAbstractModel):
    class Estrategia(models.TextChoices):
        FIFO = "fifo", "FIFO (primero en entrar, primero en salir)"
        FEFO = "fefo", "FEFO (primero en caducar, primero en salir)"

    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Cotización",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_cotizacion",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio unitario")
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name="Descuento (%)")
    lista_precio = models.ForeignKey(
        "products.ListaPrecio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Lista de precio",
        help_text="De qué lista salió el precio_unitario capturado -no se usa para calcularlo, solo se registra para reportes como la comisión por colaborador.",
    )
    estrategia_salida = models.CharField(
        max_length=10,
        choices=Estrategia.choices,
        default=Estrategia.FIFO,
        verbose_name="Estrategia de salida",
    )

    class Meta:
        verbose_name = "Detalle de cotización"
        verbose_name_plural = "Detalles de cotización"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ctd_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="ctd_precio_unitario_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                name="ctd_descuento_rango_valido",
            ),
        ]
        indexes = [
            models.Index(fields=["cotizacion"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "CTD"

    def get_slug_source(self):
        return f"{self.cotizacion_id}-{self.producto_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def subtotal(self):
        bruto = (self.cantidad or Decimal("0")) * (self.precio_unitario or Decimal("0"))
        neto = bruto * (Decimal("1") - (self.descuento or Decimal("0")) / Decimal("100"))
        return neto.quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})
        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError({"precio_unitario": "El precio unitario no puede ser negativo."})
        if self.descuento is not None and (self.descuento < 0 or self.descuento > 100):
            raise ValidationError({"descuento": "El descuento debe estar entre 0 y 100."})
