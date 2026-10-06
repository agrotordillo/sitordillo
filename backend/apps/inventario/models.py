from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from apps.core.models import BaseAbstractModel

DOS_DECIMALES = Decimal("0.01")


def redondear_costo(valor):
    """Costo unitario a 2 decimales (redondeo comercial, ROUND_HALF_UP): la
    precisión de Lote.costo_unitario y de todo costo que se copia de un lote
    (VentaDetalleLote, PedidoDetalleLote, MovimientoAlmacenDetalle). El costo
    de catálogo (Producto.precio_costo) tiene 4 decimales y un costo promedio
    puede traer decimales infinitos; sin redondear, Lote.full_clean() los
    rechaza -aun con ceros a la derecha, Decimal('12.5000')-."""
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    return valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


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

    def _normalizar_costo(self):
        """Red de seguridad para cualquier ruta que dé de alta un lote: el
        costo se redondea aquí (ver redondear_costo) antes de validarlo o
        guardarlo, igual que ya lo redondearía la base de datos. Un valor
        que ni siquiera es numérico se deja tal cual para que la validación
        normal del campo lo reporte."""
        if self.costo_unitario is None:
            return
        try:
            self.costo_unitario = redondear_costo(self.costo_unitario)
        except (InvalidOperation, TypeError, ValueError):
            pass

    def clean_fields(self, exclude=None):
        self._normalizar_costo()
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self._normalizar_costo()
        super().save(*args, **kwargs)

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
        # Apartado temporal de un pedido (ver apps.pedidos.services): igual
        # que TRASPASO, un solo tipo para ambos sentidos -negativo al
        # apartar, positivo al liberar (cancelación, edición o conversión
        # a venta, que enseguida registra su propia SALIDA)-.
        PEDIDO = "pedido", "Apartado de pedido"

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
    limite_diario_origen = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Límite diario de origen",
        help_text=(
            "Máximo del producto origen que se puede convertir en un mismo día con esta receta, sumando todas "
            "las conversiones de ese día en el mismo almacén (ej. 5 sacos/día, aunque lo normal sea convertir 2). "
            "Déjalo vacío si no aplica un límite."
        ),
    )

    class Meta:
        verbose_name = "Receta de conversión"
        verbose_name_plural = "Recetas de conversión"
        ordering = ["producto_origen__nombre", "producto_destino__nombre"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad_origen__gt=0), name="receta_cantidad_origen_positiva"),
            models.CheckConstraint(condition=models.Q(cantidad_destino__gt=0), name="receta_cantidad_destino_positiva"),
            models.CheckConstraint(
                condition=models.Q(limite_diario_origen__isnull=True) | models.Q(limite_diario_origen__gt=0),
                name="receta_limite_diario_positivo_o_nulo",
            ),
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
        if self.limite_diario_origen is not None and self.limite_diario_origen <= 0:
            raise ValidationError({"limite_diario_origen": "El límite diario debe ser mayor a cero, o déjalo vacío."})


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


class EnsamblePaquete(BaseAbstractModel):
    """Arma físicamente `cantidad` unidades de un producto tipo Paquete:
    descuenta cada componente de su receta (products.PaqueteComponente) por
    FIFO -mismo mecanismo que una venta, ver
    apps.inventario.services.registrar_ensamble_paquete- y da de alta un
    lote nuevo del paquete armado con esa cantidad, al costo real de los
    componentes que consumió.

    A diferencia del paquete "virtual" (que se arma solo al momento de
    vender, sin existencia propia -ver
    apps.ventas.services.expandir_linea-), un paquete armado aquí queda
    con existencia real: se vende directo de su propio inventario sin
    volver a tocar los componentes, que ya se descontaron aquí. Ambos
    caminos conviven para el mismo producto: si tiene existencia propia
    armada se vende de ahí, si no, se sigue armando virtualmente como
    siempre.

    Es una actividad de Almacén, igual que Conversión, sobre la que se
    modela, con una diferencia (B25 en docs/AUDITORIA.md, decisión del
    usuario): un paquete suele ser una promoción -se vende con la lista
    PROMOCION, ver products.services.resolver_precio_linea- y puede valer
    igual o menos que sus partes, así que no se exige que el valor generado
    supere al consumido. El lote armado vale exactamente lo que costaron sus
    componentes: armar no sube ni baja el valor del inventario; la promoción
    se refleja en el margen al venderlo."""

    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="ensambles_paquete",
        verbose_name="Almacén",
    )
    paquete = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="ensambles",
        verbose_name="Paquete",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad armada")
    fecha = models.DateField(verbose_name="Fecha")
    valor_consumido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor consumido",
        help_text="Costo real (FIFO) de los componentes que salieron.",
    )
    valor_generado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor generado",
        help_text="Cantidad armada × costo unitario del lote armado (el costo real de sus componentes).",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Ensamble de paquete"
        verbose_name_plural = "Ensambles de paquete"
        ordering = ["-fecha", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ensamble_cantidad_positiva"),
            models.CheckConstraint(condition=models.Q(valor_consumido__gte=0), name="ensamble_valor_consumido_no_negativo"),
            models.CheckConstraint(condition=models.Q(valor_generado__gte=0), name="ensamble_valor_generado_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["almacen"]),
            models.Index(fields=["paquete"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.cantidad} {self.paquete.nombre}"

    def get_folio_prefix(self):
        return "ENS"

    def get_slug_source(self):
        return f"{self.folio}-{self.almacen_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def costo_unitario(self):
        """Costo de cada paquete armado (el de su lote)."""
        return (self.valor_generado / self.cantidad) if self.cantidad else Decimal("0.00")

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad armada debe ser mayor a cero."})
        if self.paquete_id and self.paquete.tipo != self.paquete.TipoProducto.PAQUETE:
            raise ValidationError({"paquete": "Solo se pueden armar productos de tipo Paquete/Combo."})


class MovimientoAlmacen(BaseAbstractModel):
    """Movimiento MANUAL de almacén: entradas y salidas que no nacen de una
    compra, venta, traspaso o conversión (esas se registran solas en su
    propio módulo). Solo lo captura Compras o el Administrador.

    Se guarda en Borrador -sin tocar existencias- para poder ir agregando
    productos; al Aplicar se afecta el inventario, y Cancelar un movimiento
    aplicado registra el movimiento contrario sobre los mismos lotes (nunca
    se borra nada, igual que el resto del inventario). Toda entrada genera
    un lote nuevo valorizado al último costo de compra del producto (ver
    apps.inventario.services.ultimo_costo); toda salida descuenta por FIFO.

    `movimiento_relacionado` liga el movimiento con el que lo antecede (p.
    ej. la salida por ajuste que regulariza una entrada por ajuste
    temporal, o la entrada por devolución del proveedor que regresa una
    salida por devolución a proveedor)."""

    class Concepto(models.TextChoices):
        ENTRADA_AJUSTE = "entrada_ajuste", "Entrada por ajuste"
        ENTRADA_SOBRANTE = "entrada_sobrante", "Entrada por sobrante"
        ENTRADA_REGALIA = "entrada_regalia", "Entrada por regalía"
        ENTRADA_DEVOLUCION_PROVEEDOR = "entrada_dev_proveedor", "Entrada por devolución del proveedor"
        SALIDA_AJUSTE = "salida_ajuste", "Salida por ajuste"
        SALIDA_FALTANTE = "salida_faltante", "Salida por faltante"
        SALIDA_MERMA = "salida_merma", "Salida por merma"
        SALIDA_REGALIA = "salida_regalia", "Salida por regalía"
        SALIDA_DEVOLUCION_PROVEEDOR = "salida_dev_proveedor", "Salida por devolución a proveedor"
        SALIDA_CONSUMO = "salida_consumo", "Salida por consumo de la empresa"
        # La unidad móvil regresa al final del día lo que el cliente no
        # compró de su pedido: sale del almacén móvil y entra al almacén
        # destino en el mismo paso.
        SALIDA_DEVOLUCION_MOVIL = "salida_dev_movil", "Salida por devolución del cliente en móvil"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        APLICADO = "aplicado", "Aplicado"
        CANCELADO = "cancelado", "Cancelado"

    CONCEPTOS_ENTRADA = frozenset({
        Concepto.ENTRADA_AJUSTE,
        Concepto.ENTRADA_SOBRANTE,
        Concepto.ENTRADA_REGALIA,
        Concepto.ENTRADA_DEVOLUCION_PROVEEDOR,
    })
    CONCEPTOS_CON_PROVEEDOR = frozenset({
        Concepto.ENTRADA_REGALIA,
        Concepto.ENTRADA_DEVOLUCION_PROVEEDOR,
        Concepto.SALIDA_DEVOLUCION_PROVEEDOR,
    })

    concepto = models.CharField(max_length=30, choices=Concepto.choices, verbose_name="Concepto")
    almacen = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        related_name="movimientos_almacen",
        verbose_name="Almacén",
    )
    almacen_destino = models.ForeignKey(
        "products.Almacen",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_almacen_recibidos",
        verbose_name="Almacén destino",
        help_text="Solo para la devolución del cliente en móvil: a dónde regresa la mercancía.",
    )
    fecha = models.DateField(default=timezone.localdate, verbose_name="Fecha")
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        verbose_name="Estado",
    )
    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_almacen",
        verbose_name="Proveedor",
    )
    orden_compra = models.ForeignKey(
        "compras.OrdenCompra",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_almacen",
        verbose_name="Orden de compra relacionada",
    )
    movimiento_relacionado = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_derivados",
        verbose_name="Movimiento que lo antecede",
    )
    documento_referencia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Documento de referencia",
        help_text="Factura, nota o remisión a la que corresponde.",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    fecha_aplicacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de aplicación")
    fecha_cancelacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de cancelación")
    motivo_cancelacion = models.CharField(max_length=255, blank=True, verbose_name="Motivo de cancelación")

    class Meta:
        verbose_name = "Movimiento de almacén"
        verbose_name_plural = "Movimientos de almacén"
        ordering = ["-fecha", "-created_at"]
        indexes = [
            models.Index(fields=["concepto"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha"]),
            models.Index(fields=["almacen"]),
        ]

    def __str__(self):
        return f"{self.folio} · {self.get_concepto_display()}"

    def get_folio_prefix(self):
        return "MAL"

    def get_slug_source(self):
        return f"{self.folio}-{self.almacen_id}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def es_entrada(self):
        return self.concepto in self.CONCEPTOS_ENTRADA

    @property
    def requiere_proveedor(self):
        return self.concepto in self.CONCEPTOS_CON_PROVEEDOR

    @property
    def es_devolucion_movil(self):
        return self.concepto == self.Concepto.SALIDA_DEVOLUCION_MOVIL

    def clean(self):
        super().clean()
        errores = {}
        if self.requiere_proveedor and not self.proveedor_id:
            errores["proveedor"] = "Este concepto requiere indicar el proveedor."
        if self.es_devolucion_movil:
            if self.almacen_id and self.almacen.tipo != self.almacen.Tipo.MOVIL:
                errores["almacen"] = "La devolución en móvil sale de un almacén de tipo Móvil."
            if not self.almacen_destino_id:
                errores["almacen_destino"] = "Indica a qué almacén regresa la mercancía."
            elif self.almacen_destino_id == self.almacen_id:
                errores["almacen_destino"] = "El almacén destino debe ser distinto al almacén móvil."
        elif self.almacen_destino_id:
            errores["almacen_destino"] = "Solo la devolución del cliente en móvil lleva almacén destino."
        if self.pk and self.movimiento_relacionado_id == self.pk:
            errores["movimiento_relacionado"] = "Un movimiento no puede relacionarse consigo mismo."
        if errores:
            raise ValidationError(errores)


class MovimientoAlmacenDetalle(BaseAbstractModel):
    movimiento = models.ForeignKey(
        MovimientoAlmacen,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Movimiento de almacén",
    )
    producto = models.ForeignKey(
        "products.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_movimiento_almacen",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")
    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Costo unitario",
        help_text="Se fija al aplicar: último costo en entradas, costo promedio de los lotes consumidos en salidas.",
    )

    class Meta:
        verbose_name = "Detalle de movimiento de almacén"
        verbose_name_plural = "Detalles de movimiento de almacén"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="mad_cantidad_positiva"),
            models.UniqueConstraint(fields=["movimiento", "producto"], name="mad_producto_unico_por_movimiento"),
        ]
        indexes = [
            models.Index(fields=["movimiento"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    def get_folio_prefix(self):
        return "MAD"

    def get_slug_source(self):
        return f"{self.movimiento_id}-{self.producto_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def importe(self):
        if self.costo_unitario is None:
            return None
        return self.cantidad * self.costo_unitario

    def clean(self):
        super().clean()
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})


class MovimientoAlmacenLote(BaseAbstractModel):
    """De qué lote salió (o qué lote se creó) cada línea al aplicar el
    movimiento: es lo que permite cancelarlo regresando exactamente a los
    mismos lotes. En la devolución en móvil, `lote_destino` es el lote que
    se generó en el almacén que recibe."""

    detalle = models.ForeignKey(
        MovimientoAlmacenDetalle,
        on_delete=models.CASCADE,
        related_name="lotes",
        verbose_name="Detalle",
    )
    lote = models.ForeignKey(
        Lote,
        on_delete=models.PROTECT,
        related_name="movimientos_almacen",
        verbose_name="Lote afectado",
    )
    lote_destino = models.ForeignKey(
        Lote,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_almacen_destino",
        verbose_name="Lote generado en destino",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad")

    class Meta:
        verbose_name = "Lote de movimiento de almacén"
        verbose_name_plural = "Lotes de movimiento de almacén"
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="mal_lote_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["detalle"]),
            models.Index(fields=["lote"]),
        ]

    def __str__(self):
        return f"{self.lote} · {self.cantidad}"

    def get_folio_prefix(self):
        return "MLL"

    def get_slug_source(self):
        return f"{self.detalle_id}-{self.lote_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()
