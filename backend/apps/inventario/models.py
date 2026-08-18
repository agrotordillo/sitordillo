from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.models import BaseAbstractModel


class Lote(BaseAbstractModel):
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="lotes",
        verbose_name="Producto",
    )
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="lotes",
        verbose_name="Almacén",
    )
    orden_compra_detalle = models.ForeignKey(
        "compras.OrdenCompraDetalle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotes",
        verbose_name="Línea de orden de compra de origen",
    )
    numero_lote = models.CharField(max_length=50, blank=True, verbose_name="Número de lote")
    fecha_ingreso = models.DateField(verbose_name="Fecha de ingreso")
    fecha_caducidad = models.DateField(null=True, blank=True, verbose_name="Fecha de caducidad")
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Costo unitario")
    cantidad_inicial = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad inicial")
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad disponible")

    class Meta:
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        ordering = ["fecha_ingreso", "created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad_inicial__gt=0), name="lote_cantidad_inicial_positiva"),
            models.CheckConstraint(condition=models.Q(cantidad_disponible__gte=0), name="lote_cantidad_disponible_no_negativa"),
            models.CheckConstraint(condition=models.Q(costo_unitario__gte=0), name="lote_costo_unitario_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["producto", "almacen"]),
            models.Index(fields=["fecha_caducidad"]),
            models.Index(fields=["fecha_ingreso"]),
        ]

    def __str__(self):
        identificador = self.numero_lote or self.folio
        return f"{self.producto.nombre} · Lote {identificador} ({self.cantidad_disponible}/{self.cantidad_inicial})"

    def get_folio_prefix(self):
        return "LOT"

    def get_slug_source(self):
        return f"{self.producto_id}-{self.numero_lote or self.uuid}-{self.fecha_ingreso}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def esta_agotado(self):
        return self.cantidad_disponible <= 0

    @property
    def esta_caducado(self):
        return bool(self.fecha_caducidad and self.fecha_caducidad < timezone.localdate())

    def clean(self):
        super().clean()
        if self.cantidad_inicial is not None and self.cantidad_inicial <= 0:
            raise ValidationError({"cantidad_inicial": "La cantidad inicial debe ser mayor a cero."})
        if self.cantidad_disponible is not None and self.cantidad_disponible < 0:
            raise ValidationError({"cantidad_disponible": "La cantidad disponible no puede ser negativa."})
        if self.costo_unitario is not None and self.costo_unitario < 0:
            raise ValidationError({"costo_unitario": "El costo unitario no puede ser negativo."})


class MovimientoInventario(BaseAbstractModel):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SALIDA = "salida", "Salida"
        AJUSTE = "ajuste", "Ajuste"
        MERMA = "merma", "Merma"
        TRASPASO = "traspaso", "Traspaso"
        DEVOLUCION = "devolucion", "Devolución de cliente"

    lote = models.ForeignKey(
        Lote,
        on_delete=models.PROTECT,
        related_name="movimientos",
        verbose_name="Lote",
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Tipo de movimiento")
    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Cantidad (con signo)",
    )
    cantidad_anterior = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad disponible antes")
    cantidad_nueva = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad disponible después")
    motivo = models.CharField(max_length=255, blank=True, verbose_name="Motivo")
    fecha_movimiento = models.DateTimeField(default=timezone.now, verbose_name="Fecha del movimiento")

    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
        ordering = ["-fecha_movimiento"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(cantidad=0), name="movimiento_cantidad_no_cero"),
        ]
        indexes = [
            models.Index(fields=["lote"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["fecha_movimiento"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad} · {self.lote}"

    def get_folio_prefix(self):
        return "MOV"

    def get_slug_source(self):
        return f"{self.lote_id}-{self.tipo}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.cantidad is None or self.cantidad == 0:
            raise ValidationError({"cantidad": "La cantidad del movimiento no puede ser cero."})
        if self.tipo == self.Tipo.ENTRADA and self.cantidad <= 0:
            raise ValidationError({"cantidad": "Una entrada debe registrarse con cantidad positiva."})
        if self.tipo in (self.Tipo.SALIDA, self.Tipo.MERMA) and self.cantidad >= 0:
            raise ValidationError({"cantidad": "Una salida o merma debe registrarse con cantidad negativa."})
