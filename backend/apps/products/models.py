from decimal import Decimal
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


class Proveedor(BaseAbstractModel):
    nombre = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Nombre del proveedor",
        error_messages={"unique": "Ya existe una %(model_name)s con este nombre."},
    )
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "PRV"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


class Almacen(BaseAbstractModel):
    nombre = models.CharField(max_length=200)

    class Meta:
        verbose_name = "Almacén"
        verbose_name_plural = "Almacenes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def get_folio_prefix(self):
        return "ALM"

    def get_slug_source(self):
        return self.nombre

    @property
    def display_name(self):
        return self.nombre.strip()


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


class Producto(BaseAbstractModel):
    class TipoProducto(models.TextChoices):
        PRODUCTO = "producto", "Producto"
        SERVICIO = "servicio", "Servicio"
        INSUMO = "insumo", "Insumo"

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
        Proveedor,
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
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    notas = models.TextField(blank=True, verbose_name="Notas")
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Precio de costo")
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Precio de venta")
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Stock mínimo")
    stock_maximo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Stock máximo")

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
        ]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["nombre"]),
            models.Index(fields=["marca"]),
            models.Index(fields=["proveedor"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["subcategoria"]),
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