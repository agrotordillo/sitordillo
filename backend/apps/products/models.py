from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from apps.core.models import BaseAbstractModel

class Categoria(BaseAbstractModel):
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la categoría", unique=True, error_messages={"unique": "Ya existe una %(model_name)s con este nombre."})
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "CAT"
    
    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

class Subcategoria(BaseAbstractModel):
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la subcategoría")
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name="subcategorias",
        verbose_name="Categoría padre",
    )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Subcategoría"
        verbose_name_plural = "Subcategorías"
        ordering = ["categoria__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["categoria", "nombre"], name="unique_subcategoria_por_categoria"),
        ]
        indexes = [
            models.Index(fields=["categoria"]),
            models.Index(fields=["nombre"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"

    def get_folio_prefix(self):
        return "SUB"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Linea(BaseAbstractModel):
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre de la línea",
        unique=True,
        error_messages={"unique": "Ya existe una %(model_name)s con este nombre."},
    )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Línea"
        verbose_name_plural = "Líneas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "LIN"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Marca(BaseAbstractModel):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de la marca",
        error_messages={"unique": "Ya existe una %(model_name)s con este nombre."},
    )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "MRC"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Almacen(BaseAbstractModel):
    class Tipo(models.TextChoices):
        CEDIS = "cedis", "CEDIS"
        SUCURSAL = "sucursal", "Sucursal"

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.SUCURSAL,
        verbose_name="Tipo de almacén",
    )

    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo"],
                condition=models.Q(tipo="cedis"),
                name="unico_cedis",
            ),
        ]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "ALM"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

    def clean(self):
        super().clean()
        if self.tipo == self.Tipo.CEDIS:
            ya_existe = Almacen.objects.filter(tipo=self.Tipo.CEDIS).exclude(pk=self.pk).exists()
            if ya_existe:
                raise ValidationError({"tipo": "Ya existe un almacén CEDIS; solo puede haber uno."})


class UnidadMedida(BaseAbstractModel):
    nombre = models.CharField(max_length=80, unique=True, verbose_name="Nombre de la unidad")
    abreviatura = models.CharField(max_length=10, unique=True, verbose_name="Abreviatura")

    class Meta:
        verbose_name = "Unidad de medida"
        verbose_name_plural = "Unidades de medida"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"

    def get_folio_prefix(self):
        return "UMD"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class ListaPrecio(BaseAbstractModel):
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de la lista de precios",
        error_messages={"unique": "Ya existe una %(model_name)s con este nombre."},
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden de despliegue")

    class Meta:
        verbose_name = "Lista de precios"
        verbose_name_plural = "Listas de precios"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "LSP"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Producto(BaseAbstractModel):
    class TipoProducto(models.TextChoices):
        PRODUCTO = "producto", "Producto"
        SERVICIO = "servicio", "Servicio"
        INSUMO = "insumo", "Insumo"
        PAQUETE = "paquete", "Paquete/Combo"

    class TipoIVA(models.TextChoices):
        GRAVADO = "gravado", "Gravado"
        EXENTO = "exento", "Exento"

    class Costeo(models.TextChoices):
        MANUAL = "manual", "Manual"
        ULTIMO = "ultimo", "Último costo"
        PROMEDIO = "promedio", "Costo promedio"

    nombre = models.CharField(max_length=200, verbose_name="Nombre del producto")
    sku = models.CharField(max_length=30, unique=True, verbose_name="SKU")
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Código de barras")
    marca = models.ForeignKey(
        Marca,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Marca",
    )
    proveedor = models.ForeignKey(
        "proveedores.Proveedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Proveedor",
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Categoría",
    )
    subcategoria = models.ForeignKey(
        Subcategoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Subcategoría",
    )
    linea = models.ForeignKey(
        Linea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Línea",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoProducto.choices,
        default=TipoProducto.PRODUCTO,
        verbose_name="Tipo de producto",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Unidad de medida",
    )
    almacen = models.ForeignKey(
        Almacen,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paquetes",
        verbose_name="Sucursal (solo para paquetes)",
        help_text="La sucursal que arma este paquete/combo. Solo aplica cuando el tipo es Paquete/Combo.",
    )
    clave_prod_serv_sat = models.ForeignKey(
        "fiscal.ClaveProdServSAT",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Clave de producto o servicio SAT",
        help_text="Requerida para poder facturar este producto (CFDI).",
    )
    clave_unidad_sat = models.ForeignKey(
        "fiscal.ClaveUnidadSAT",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="productos",
        verbose_name="Clave de unidad SAT",
        help_text="Requerida para poder facturar este producto (CFDI).",
    )
    tipo_iva = models.CharField(
        max_length=10,
        choices=TipoIVA.choices,
        default=TipoIVA.GRAVADO,
        verbose_name="IVA",
    )
    tasa_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("16.00"),
        verbose_name="Tasa de IVA (%)",
        help_text="Solo aplica cuando el IVA es Gravado; varía según el producto (16%, 8% zona fronteriza, etc.).",
    )
    aplica_ieps = models.BooleanField(default=False, verbose_name="Aplica IEPS")
    tasa_ieps = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Tasa de IEPS (%)",
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    notas = models.TextField(blank=True, verbose_name="Notas")
    costeo = models.CharField(
        max_length=10,
        choices=Costeo.choices,
        default=Costeo.MANUAL,
        verbose_name="Método de costeo",
        help_text="Cómo se actualiza el costo del producto a partir de las compras.",
    )
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Precio de costo")
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Precio de venta")
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Stock mínimo")
    stock_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Stock máximo")
    peso = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="Peso (kg)")
    dias_reserva = models.PositiveIntegerField(
        default=0,
        verbose_name="Días de reserva",
        help_text="Días que tarda el proveedor en entregar después del pedido.",
    )
    codigo_proveedor = models.CharField(max_length=50, blank=True, verbose_name="Código de proveedor")
    imagen = models.ImageField(upload_to="productos/", null=True, blank=True, verbose_name="Imagen")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="unique_producto_nombre_ci"),
            models.CheckConstraint(condition=models.Q(precio_costo__gte=0), name="producto_precio_costo_no_negativo"),
            models.CheckConstraint(condition=models.Q(precio_venta__gte=0), name="producto_precio_venta_no_negativo"),
            models.CheckConstraint(condition=models.Q(stock_minimo__gte=0), name="producto_stock_minimo_no_negativo"),
            models.CheckConstraint(condition=models.Q(stock_maximo__gte=0), name="producto_stock_maximo_no_negativo"),
            models.CheckConstraint(condition=models.Q(stock_maximo__gte=models.F("stock_minimo")), name="producto_stock_maximo_mayor_igual_minimo"),
            models.CheckConstraint(condition=models.Q(tasa_iva__gte=0), name="producto_tasa_iva_no_negativa"),
            models.CheckConstraint(
                condition=models.Q(tasa_ieps__isnull=True) | models.Q(tasa_ieps__gte=0),
                name="producto_tasa_ieps_no_negativa",
            ),
            models.CheckConstraint(
                condition=models.Q(peso__isnull=True) | models.Q(peso__gte=0),
                name="producto_peso_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["nombre"]),
            models.Index(fields=["marca"]),
            models.Index(fields=["proveedor"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["subcategoria"]),
            models.Index(fields=["linea"]),
            models.Index(fields=["tipo"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.sku})"

    def get_folio_prefix(self):
        return "PDT"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()

    @property
    def es_paquete(self):
        return self.tipo == self.TipoProducto.PAQUETE

    def clean(self):
        super().clean()
        if self.subcategoria and self.categoria and self.subcategoria.categoria_id != self.categoria_id:
            raise ValidationError({"subcategoria": "La subcategoría seleccionada no pertenece a la categoría indicada."})
        if self.precio_costo < 0:
            raise ValidationError({"precio_costo": "El precio de costo no puede ser negativo."})
        if self.precio_venta < 0:
            raise ValidationError({"precio_venta": "El precio de venta no puede ser negativo."})
        if self.stock_minimo < 0:
            raise ValidationError({"stock_minimo": "El stock mínimo no puede ser negativo."})
        if self.stock_maximo < 0:
            raise ValidationError({"stock_maximo": "El stock máximo no puede ser negativo."})
        if self.stock_maximo < self.stock_minimo:
            raise ValidationError({"stock_maximo": "El stock máximo debe ser mayor o igual al stock mínimo."})

        if self.tipo == self.TipoProducto.PAQUETE:
            if not self.almacen_id:
                raise ValidationError({"almacen": "Indica la sucursal que arma este paquete."})
            if self.almacen.tipo != Almacen.Tipo.SUCURSAL:
                raise ValidationError({"almacen": "Un paquete solo puede pertenecer a una sucursal, no al CEDIS."})
        elif self.almacen_id:
            raise ValidationError({"almacen": "Solo los paquetes/combos pueden pertenecer a una sucursal."})

        if self.tipo_iva == self.TipoIVA.EXENTO:
            self.tasa_iva = Decimal("0.00")
        elif self.tasa_iva is None or self.tasa_iva < 0:
            # Gravado admite tasa 0% ("tasa cero", Art. 2-A LIVA: productos
            # agropecuarios, veterinarios, etc.) — distinto de Exento.
            raise ValidationError({"tasa_iva": "Indica la tasa de IVA para un producto gravado."})

        if self.aplica_ieps:
            if not self.tasa_ieps or self.tasa_ieps <= 0:
                raise ValidationError({"tasa_ieps": "Indica la tasa de IEPS."})
        elif self.tasa_ieps:
            raise ValidationError({"aplica_ieps": "Activa 'Aplica IEPS' antes de definir su tasa."})

    def save(self, *args, **kwargs):
        costo_anterior = None
        if self.pk:
            costo_anterior = (
                Producto.objects.filter(pk=self.pk).values_list("precio_costo", flat=True).first()
            )
        super().save(*args, **kwargs)
        if costo_anterior is not None and costo_anterior != self.precio_costo:
            self._recalcular_precios_por_utilidad()

    def _recalcular_precios_por_utilidad(self):
        """Cuando cambia el costo del producto, recalcula el precio de cada
        lista que tenga un % de utilidad guardado (precio_sin_impuesto =
        costo * (1 + utilidad% / 100)). Las filas sin % de utilidad son
        precio manual y no se tocan."""
        for precio in self.precios.filter(utilidad_pct__isnull=False):
            precio.producto = self
            factor = (Decimal("1") + precio._tasa_ieps) * (Decimal("1") + precio._tasa_iva)
            precio_sin_impuesto = self.precio_costo * (Decimal("1") + precio.utilidad_pct / Decimal("100"))
            precio.precio_con_impuesto = (precio_sin_impuesto * factor).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            precio.save(update_fields=["precio_con_impuesto"])


class PaqueteComponente(BaseAbstractModel):
    """Producto (tipo=paquete) y los productos reales que lo componen.
    El paquete se vende como una sola línea; al momento de la venta se
    descuenta inventario de cada componente, no del paquete en sí."""

    paquete = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="componentes",
        verbose_name="Paquete",
    )
    producto_componente = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="usado_en_paquetes",
        verbose_name="Producto componente",
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cantidad por paquete")

    class Meta:
        verbose_name = "Componente de paquete"
        verbose_name_plural = "Componentes de paquete"
        ordering = ["paquete", "producto_componente__nombre"]
        constraints = [
            models.UniqueConstraint(fields=["paquete", "producto_componente"], name="unico_componente_por_paquete"),
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="paquete_componente_cantidad_positiva"),
        ]
        indexes = [
            models.Index(fields=["paquete"]),
            models.Index(fields=["producto_componente"]),
        ]

    def __str__(self):
        return f"{self.producto_componente.nombre} x{self.cantidad} (en {self.paquete.nombre})"

    def get_folio_prefix(self):
        return "PQC"

    def get_slug_source(self):
        return f"{self.paquete_id}-{self.producto_componente_id}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    def clean(self):
        super().clean()
        if self.paquete_id and self.paquete.tipo != Producto.TipoProducto.PAQUETE:
            raise ValidationError({"paquete": "Este producto no es de tipo Paquete/Combo."})
        if self.producto_componente_id and self.producto_componente.tipo == Producto.TipoProducto.PAQUETE:
            raise ValidationError({
                "producto_componente": "Un paquete no puede tener como componente a otro paquete.",
            })
        if self.paquete_id and self.producto_componente_id and self.paquete_id == self.producto_componente_id:
            raise ValidationError({"producto_componente": "Un paquete no puede incluirse a sí mismo como componente."})
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor a cero."})


class ProductoPrecio(BaseAbstractModel):
    """Precio de un producto para una lista de precios y, opcionalmente,
    una sucursal específica. Si `almacen` es nulo el precio es general
    (aplica a cualquier sucursal); si se asigna, es un precio específico
    para esa sucursal que tiene prioridad sobre el general de la misma
    lista. `precio_con_impuesto` es la única fuente de verdad — sigue la
    misma convención que VentaDetalle.precio_unitario y
    facturacion.factura_service._desglosar_linea() (precio con impuestos
    incluidos, se desglosa hacia atrás). `utilidad_pct` es solo una
    referencia de captura, no se recalcula sola si cambia el costo."""

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="precios",
        verbose_name="Producto",
    )
    lista_precio = models.ForeignKey(
        ListaPrecio,
        on_delete=models.PROTECT,
        related_name="precios_producto",
        verbose_name="Lista de precios",
    )
    almacen = models.ForeignKey(
        Almacen,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="precios_producto",
        verbose_name="Sucursal",
        help_text="Si se deja vacío, el precio aplica a todas las sucursales.",
    )
    utilidad_pct = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Porcentaje de utilidad",
    )
    precio_con_impuesto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio de venta (con impuesto)")

    class Meta:
        verbose_name = "Precio de producto"
        verbose_name_plural = "Precios de producto"
        ordering = ["producto__nombre", "lista_precio__orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "lista_precio", "almacen"],
                condition=models.Q(almacen__isnull=False),
                name="unico_precio_por_lista_y_sucursal",
            ),
            models.UniqueConstraint(
                fields=["producto", "lista_precio"],
                condition=models.Q(almacen__isnull=True),
                name="unico_precio_por_lista_general",
            ),
            models.CheckConstraint(condition=models.Q(precio_con_impuesto__gte=0), name="producto_precio_con_impuesto_no_negativo"),
        ]
        indexes = [
            models.Index(fields=["producto"]),
            models.Index(fields=["lista_precio"]),
            models.Index(fields=["almacen"]),
        ]

    def __str__(self):
        sucursal = f" ({self.almacen.nombre})" if self.almacen_id else ""
        return f"{self.producto.nombre} · {self.lista_precio.nombre}{sucursal}: {self.precio_con_impuesto}"

    def get_folio_prefix(self):
        return "PPR"

    def get_slug_source(self):
        return f"{self.producto_id}-{self.lista_precio_id}-{self.almacen_id or 'gral'}-{self.uuid}"

    @property
    def display_name(self):
        return self.__str__()

    @property
    def _tasa_iva(self):
        return (self.producto.tasa_iva / Decimal("100")) if self.producto.tipo_iva == Producto.TipoIVA.GRAVADO else Decimal("0")

    @property
    def _tasa_ieps(self):
        return (self.producto.tasa_ieps / Decimal("100")) if self.producto.aplica_ieps and self.producto.tasa_ieps else Decimal("0")

    @property
    def precio_sin_impuesto(self):
        factor = (Decimal("1") + self._tasa_ieps) * (Decimal("1") + self._tasa_iva)
        return (self.precio_con_impuesto / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def importe_ieps(self):
        return (self.precio_sin_impuesto * self._tasa_ieps).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def importe_iva(self):
        return ((self.precio_sin_impuesto + self.importe_ieps) * self._tasa_iva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def importe_utilidad(self):
        return self.precio_sin_impuesto - self.producto.precio_costo

    def clean(self):
        super().clean()
        if self.precio_con_impuesto is not None and self.precio_con_impuesto < 0:
            raise ValidationError({"precio_con_impuesto": "El precio de venta no puede ser negativo."})