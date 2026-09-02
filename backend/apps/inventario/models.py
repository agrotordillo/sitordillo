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


class RecetaConversion(BaseAbstractModel):
    """Equivalencia para transformar un producto en otro dentro del mismo
    almacén (p. ej. 1 saco de maíz de 40kg -> 20 bolsas de 2kg). Es un
    catálogo reusable -no se captura la equivalencia a mano en cada
    conversión- para evitar errores de captura y mantener consistencia."""

    producto_origen = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="recetas_conversion_origen",
        verbose_name="Producto origen",
    )
    producto_destino = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="recetas_conversion_destino",
        verbose_name="Producto destino",
    )
    cantidad_origen = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad origen")
    cantidad_destino = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad destino")

    class Meta:
        verbose_name = "Receta de conversión"
        verbose_name_plural = "Recetas de conversión"
        ordering = ["producto_origen__nombre", "producto_destino__nombre"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad_origen__gt=0), name="receta_cantidad_origen_positiva"),
            models.CheckConstraint(condition=models.Q(cantidad_destino__gt=0), name="receta_cantidad_destino_positiva"),
            models.UniqueConstraint(
                fields=["producto_origen", "producto_destino"], name="receta_unica_por_par_de_productos"
            ),
        ]
        indexes = [
            models.Index(fields=["producto_origen"]),
            models.Index(fields=["producto_destino"]),
        ]

    def __str__(self):
        return f"{self.producto_origen.nombre} → {self.producto_destino.nombre}"

    def get_folio_prefix(self):
        return "RCV"

    def get_slug_source(self):
        return f"{self.producto_origen_id}-{self.producto_destino_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def factor(self):
        """Cuánto producto destino se genera por cada unidad de producto
        origen (ej. 20 bolsas por saco)."""
        return self.cantidad_destino / self.cantidad_origen

    def clean(self):
        super().clean()
        if self.producto_origen_id and self.producto_origen_id == self.producto_destino_id:
            raise ValidationError({"producto_destino": "El producto destino debe ser distinto al producto origen."})
        if self.cantidad_origen is not None and self.cantidad_origen <= 0:
            raise ValidationError({"cantidad_origen": "La cantidad origen debe ser mayor a cero."})
        if self.cantidad_destino is not None and self.cantidad_destino <= 0:
            raise ValidationError({"cantidad_destino": "La cantidad destino debe ser mayor a cero."})


class Conversion(BaseAbstractModel):
    """Transforma `cantidad_origen_convertida` del producto origen de una
    receta en el producto destino correspondiente, dentro de un almacén: es
    una actividad propia de Almacén, nunca al revés (siempre de presentación
    grande a chica, ver RecetaConversion). El producto origen sale por FIFO
    (mismo mecanismo que una venta, ver apps.inventario.services.
    registrar_conversion), así que `valor_consumido` es el costo real; el
    producto destino entra a su costo de catálogo, de donde sale
    `valor_generado`. Envasar siempre debe costar más que vender a granel
    (empaque, mano de obra), así que se rechaza una conversión donde el
    valor generado no supere al valor consumido -si pasa, hay un costo de
    catálogo mal capturado."""

    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="conversiones",
        verbose_name="Almacén",
    )
    receta = models.ForeignKey(
        RecetaConversion,
        on_delete=models.PROTECT,
        related_name="conversiones",
        verbose_name="Receta",
    )
    cantidad_origen_convertida = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Cantidad de origen convertida"
    )
    cantidad_destino_generada = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Cantidad de destino generada"
    )
    fecha = models.DateField(verbose_name="Fecha")
    valor_consumido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor consumido",
        help_text="Costo real (FIFO) del producto origen que salió.",
    )
    valor_generado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor generado",
        help_text="Cantidad destino × costo de catálogo del producto destino.",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Conversión"
        verbose_name_plural = "Conversiones"
        ordering = ["-fecha", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad_origen_convertida__gt=0), name="conversion_cantidad_origen_positiva"
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_destino_generada__gt=0), name="conversion_cantidad_destino_positiva"
            ),
            models.CheckConstraint(condition=models.Q(valor_consumido__gte=0), name="conversion_valor_consumido_no_negativo"),
            models.CheckConstraint(condition=models.Q(valor_generado__gte=0), name="conversion_valor_generado_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["almacen"]),
            models.Index(fields=["receta"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.receta}"

    def get_folio_prefix(self):
        return "CNV"

    def get_slug_source(self):
        return f"{self.folio}-{self.almacen_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def diferencia(self):
        return self.valor_generado - self.valor_consumido

    def clean(self):
        super().clean()
        if self.cantidad_origen_convertida is not None and self.cantidad_origen_convertida <= 0:
            raise ValidationError({"cantidad_origen_convertida": "La cantidad a convertir debe ser mayor a cero."})
        if (
            self.valor_generado is not None
            and self.valor_consumido is not None
            and self.valor_generado <= self.valor_consumido
        ):
            raise ValidationError({
                "valor_generado": (
                    "El valor generado debe superar al valor consumido: envasar siempre cuesta más que vender a "
                    "granel. Revisa el costo de catálogo del producto destino."
                ),
            })
