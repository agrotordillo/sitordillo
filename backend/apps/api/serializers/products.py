from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Producto


class OptionSerializer(serializers.Serializer):
    value = serializers.IntegerField(source="id")
    label = serializers.CharField(source="nombre")


class ActualizarCostoSerializer(serializers.Serializer):
    """Mismo rango y precisión que Producto.precio_costo: rechaza texto,
    NaN/infinito, negativos o más de 4 decimales con un 400 en vez de un
    error 500."""

    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    precio_costo = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"))
