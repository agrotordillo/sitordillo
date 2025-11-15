# django imports
from django.db import models
# local imports
from apps.core.models import BaseAbstractModel


class Category(BaseAbstractModel):
    """Modelo para las categorías de productos."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_folio_prefix(self):
        return "CAT"


class Product(BaseAbstractModel):
    """Modelo para los productos."""

    PRODUCT_TYPE_CHOICES = [
        ("product", "Simple product"),
        ("bundle", "Product bundle / kit"),
        ("service", "Service"),
    ]

    sku = models.CharField(
        max_length=30,
        unique=True,
        help_text="Internal inventory code (Stock Keeping Unit)."
    )
    barcode = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text="EAN/UPC barcode if applicable."
    )
    name = models.CharField(max_length=255)
    product_type = models.CharField(
        max_length=20, choices=PRODUCT_TYPE_CHOICES, default="product"
    )
    # category = models.ForeignKey(
    #     Category,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="products"
    # )
    brand = models.CharField(max_length=100, blank=True, null=True)
    base_unit = models.CharField(max_length=50, help_text="e.g. piece, sack, liter")
    aux_unit = models.CharField(
        max_length=50, blank=True, null=True, help_text="e.g. kg, ml"
    )
    aux_factor = models.DecimalField(
        max_digits=10, decimal_places=2, default=1, help_text="Conversion factor."
    )
    weight_kg = models.DecimalField(
        max_digits=10, decimal_places=3, default=0, help_text="Weight in kilograms."
    )
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=16.00, help_text="IVA percentage."
    )
    global_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_stockable = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_folio_prefix(self):
        return "PDT"

    def get_slug_source(self):
        return self.name
