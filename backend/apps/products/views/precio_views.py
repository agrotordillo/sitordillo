from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Producto
from apps.products.forms import ProductoPrecioFormSet


@permission_required("products.change_productoprecio", raise_exception=True)
def producto_precios_view(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        formset = ProductoPrecioFormSet(request.POST, instance=producto, prefix="precios")
        if formset.is_valid():
            try:
                with transaction.atomic():
                    formset.save()
            except IntegrityError:
                messages.error(
                    request,
                    "No fue posible guardar: hay una lista de precios/sucursal repetida entre las filas.",
                )
            else:
                messages.success(request, "Precios del producto actualizados correctamente.")
                return redirect("products:product-list")
    else:
        formset = ProductoPrecioFormSet(instance=producto, prefix="precios")

    return render(
        request,
        "products/producto_precios_form.html",
        {"producto": producto, "formset": formset, "active_module": "products"},
    )
