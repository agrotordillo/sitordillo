from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from apps.core.models import BaseAbstractModel


class Pedido(BaseAbstractModel):
    """Mismo flujo de mostrador que una Cotización (turno propio y abierto,
    sucursal y folio tomados de ahí, precio que no captura mostrador), con
    una diferencia: al guardarse APARTA el inventario de la sucursal -un
    traspaso temporal, ver apps.pedidos.services.apartar_inventario- para
    que nadie más venda esa mercancía mientras el cliente pasa a caja o
    vuelve por ella. Se cierra de una de dos formas: caja lo convierte en
    venta (tal cual, sin modificar líneas) o se cancela y el inventario
    regresa a los mismos lotes de donde salió."""

    class Estatus(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        CONVERTIDO = "convertido", "Convertido a venta"
        CANCELADO = "cancelado", "Cancelado"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="Cliente",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="Sucursal",
    )
    punto_venta = models.ForeignKey(
        "products.PuntoVenta",
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="Punto de venta",
    )
    turno = models.ForeignKey(
        "products.Turno",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pedidos",
        verbose_name="Turno",
        help_text="El turno propio y abierto de quien lo levantó, tomado automáticamente "
        "(ver products.services.turno_abierto_de). No lo elige el usuario.",
    )
    numero_documento = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="Número de pedido",
        help_text="Folio para el cliente: número de almacén + número de punto de venta + \"P\" + consecutivo. Se genera solo al guardar y no se puede editar.",
    )
    fecha_pedido = models.DateTimeField(default=timezone.now, verbose_name="Fecha de pedido")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.ABIERTO,
        verbose_name="Estatus",
    )
    venta = models.OneToOneField(
        "ventas.Venta",
        on_delete=models.SET_NULL,
        related_name="pedido_origen",
        null=True,
        blank=True,
        verbose_name="Venta generada",
    )
    fecha_cancelacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de cancelación")
    motivo_cancelacion = models.CharField(max_length=255, blank=True, verbose_name="Motivo de cancelación")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-fecha_pedido"]
        permissions = [
            ("cancelar_pedido", "Puede cancelar un pedido y liberar su inventario apartado"),
        ]
        indexes = [
            models.Index(fields=["cliente"]),
            models.Index(fields=["almacen"]),
            models.Index(fields=["estatus"]),
            models.Index(fields=["punto_venta"], name="pedidos_punto_venta_idx"),
        ]

    def __str__(self):
        return f"{self.numero_documento or self.folio} · {self.cliente.display_name}"

    def get_folio_prefix(self):
        return "PED"

    def get_slug_source(self):
        return f"{self.folio}-{self.cliente_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def esta_abierto(self):
        return self.estatus == self.Estatus.ABIERTO

    @property
    def subtotal(self):
        return sum((detalle.subtotal for detalle in self.detalles.all()), Decimal("0.00"))

    @property
    def total(self):
        return self.subtotal

    def clean(self):
        super().clean()
        if self.almacen_id and self.almacen.tipo != self.almacen.Tipo.SUCURSAL:
            raise ValidationError({"almacen": "Los pedidos se registran desde una sucursal, no desde el CEDIS."})
        if self.almacen_id and self.punto_venta_id and self.punto_venta.almacen_id != self.almacen_id:
            raise ValidationError({"punto_venta": "El punto de venta debe pertenecer a la sucursal seleccionada."})

    def save(self, *args, **kwargs):
        if not self.numero_documento and self.punto_venta_id:
            from apps.products.models import PuntoVenta

            with transaction.atomic():
                punto_venta = (
                    PuntoVenta.objects.select_for_update().select_related("almacen").get(pk=self.punto_venta_id)
                )
                self.numero_documento = punto_venta.tomar_siguiente_folio_pedido()
        super().save(*args, **kwargs)


class PedidoDetalle(BaseAbstractModel):
    class Estrategia(models.TextChoices):
        FIFO = "fifo", "FIFO (primero en entrar, primero en salir)"
        FEFO = "fefo", "FEFO (primero en caducar, primero en salir)"

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Pedido",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_pedido",
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
        verbose_name = "Detalle de pedido"
        verbose_name_plural = "Detalles de pedido"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="pdd_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="pdd_precio_unitario_no_negativo"),
            models.CheckConstraint(
                condition=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                name="pdd_descuento_rango_valido",
            ),
        ]
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "PDD"

    def get_slug_source(self):
        return f"{self.pedido_id}-{self.producto_id}-{self.uuid}"

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


class PedidoDetalleLote(BaseAbstractModel):
    """De qué lote(s) se apartó cada línea del pedido (el "traspaso
    temporal"), con el costo de ese momento -igual que TraspasoLote guarda
    el lote de origen-. Es lo que permite regresar exactamente esa
    mercancía a los mismos lotes al cancelar, o pasarla tal cual a
    VentaDetalleLote al convertir el pedido en venta. Una fila existe
    mientras la mercancía sigue apartada: al liberarla (cancelación o
    edición) se borra; al convertir a venta se conserva como historial."""

    detalle = models.ForeignKey(
        PedidoDetalle,
        on_delete=models.CASCADE,
        related_name="lotes",
        verbose_name="Detalle de pedido",
    )
    lote = models.ForeignKey(
        "inventario.Lote",
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="Lote de origen",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad apartada")
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Costo unitario al momento de apartar")

    class Meta:
        verbose_name = "Lote de pedido"
        verbose_name_plural = "Lotes de pedido"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="pdl_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["detalle"]),
            models.Index(fields=["lote"]),
        ]

    def __str__(self):
        return f"{self.lote} → {self.cantidad}"

    def get_folio_prefix(self):
        return "PDL"

    def get_slug_source(self):
        return f"{self.detalle_id}-{self.lote_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()
