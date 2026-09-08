from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Producto
from apps.products.forms import ProductoStockSucursalFormSet


@permission_required("products.change_productostocksucursal", raise_exception=True)
def producto_stock_sucursal_view(request, pk):
    """Captura el mínimo/máximo de existencia de este producto por
    sucursal -no hace falta llenarlo para todos los productos, solo para
    los que se quieran vigilar en el análisis de surtimiento (ver
    inventario:surtimiento-list)."""
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        formset = ProductoStockSucursalFormSet(request.POST, instance=producto, prefix="stock")
        if formset.is_valid():
            try:
                with transaction.atomic():
                    formset.save()
            except IntegrityError:
                messages.error(request, "No fue posible guardar: hay una sucursal repetida entre las filas.")
            else:
                messages.success(request, "Mínimos y máximos por sucursal actualizados correctamente.")
                return redirect("products:product-list")
    else:
        formset = ProductoStockSucursalFormSet(instance=producto, prefix="stock")

    return render(
        request,
        "products/producto_stock_sucursal_form.html",
        {"producto": producto, "formset": formset, "active_module": "products"},
    )
