from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import BaseAbstractModel


class Traspaso(BaseAbstractModel):
    class Estatus(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADO = "enviado", "Enviado"
        RECIBIDO = "recibido", "Recibido"
        CANCELADO = "cancelado", "Cancelado"

    almacen_origen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="traspasos_enviados",
        verbose_name="Almacén origen",
    )
    almacen_destino = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="traspasos_recibidos",
        verbose_name="Almacén destino",
    )
    fecha_envio = models.DateField(verbose_name="Fecha de envío")
    fecha_recepcion = models.DateField(null=True, blank=True, verbose_name="Fecha de recepción")
    estatus = models.CharField(
        max_length=10,
        choices=Estatus.choices,
        default=Estatus.BORRADOR,
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Traspaso"
        verbose_name_plural = "Traspasos"
        ordering = ["-fecha_envio", "-created_at"]
        indexes = [
            models.Index(fields=["almacen_origen"]),
            models.Index(fields=["almacen_destino"]),
            models.Index(fields=["estatus"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.almacen_origen.nombre} → {self.almacen_destino.nombre}"

    def get_folio_prefix(self):
        return "TRP"

    def get_slug_source(self):
        return f"{self.folio}-{self.almacen_origen_id}-{self.almacen_destino_id}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.almacen_origen_id and self.almacen_origen_id == self.almacen_destino_id:
            raise ValidationError({"almacen_destino": "El almacén destino debe ser distinto al de origen."})
        if self.almacen_origen_id and self.almacen_origen.tipo != self.almacen_origen.Tipo.CEDIS:
            raise ValidationError({"almacen_origen": "El almacén origen de un traspaso debe ser el CEDIS."})
        if self.almacen_destino_id and self.almacen_destino.tipo != self.almacen_destino.Tipo.SUCURSAL:
            raise ValidationError({"almacen_destino": "El almacén destino de un traspaso debe ser una sucursal."})


class TraspasoDetalle(BaseAbstractModel):
    class Estrategia(models.TextChoices):
        FIFO = "fifo", "FIFO (primero en entrar, primero en salir)"
        FEFO = "fefo", "FEFO (primero en caducar, primero en salir)"

    traspaso = models.ForeignKey(
        Traspaso,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Traspaso",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_traspaso",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad solicitada")
    estrategia_salida = models.CharField(
        max_length=10,
        choices=Estrategia.choices,
        default=Estrategia.FIFO,
        verbose_name="Estrategia de salida",
    )

    class Meta:
        verbose_name = "Detalle de traspaso"
        verbose_name_plural = "Detalles de traspaso"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="trd_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["traspaso"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "TRD"

    def get_slug_source(self):
        return f"{self.traspaso_id}-{self.producto_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})


class TraspasoLote(BaseAbstractModel):
    detalle = models.ForeignKey(
        TraspasoDetalle,
        on_delete=models.CASCADE,
        related_name="lotes",
        verbose_name="Detalle de traspaso",
    )
    lote_origen = models.ForeignKey(
        "inventario.Lote",
        on_delete=models.PROTECT,
        related_name="traspasos_salida",
        verbose_name="Lote de origen",
    )
    lote_destino = models.ForeignKey(
        "inventario.Lote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="traspaso_origen",
        verbose_name="Lote generado en destino",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad transferida")

    class Meta:
        verbose_name = "Lote de traspaso"
        verbose_name_plural = "Lotes de traspaso"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="trl_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["detalle"]),
            models.Index(fields=["lote_origen"]),
        ]

    def __str__(self):
        return f"{self.lote_origen} → {self.cantidad}"

    def get_folio_prefix(self):
        return "TRL"

    def get_slug_source(self):
        return f"{self.detalle_id}-{self.lote_origen_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def recibido(self):
        return self.lote_destino_id is not None
