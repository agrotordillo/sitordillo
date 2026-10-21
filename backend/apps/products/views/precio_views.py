from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Producto
from apps.products.forms import PreciosBaseProductoForm, ProductoPrecioFormSet


@permission_required("products.change_productoprecio", raise_exception=True)
def producto_precios_view(request, pk):
    """Precios por lista del producto, y también su precio de costo y de
    venta (solo editables con permiso de cambiar productos, igual que en la
    edición del producto). El costo se guarda sin el recálculo automático de
    las listas: si el usuario confirmó actualizarlas, ya vienen recalculadas
    en el formset. Al final el precio de venta toma el de Público general,
    como siempre que se guardan los precios de lista."""
    producto = get_object_or_404(Producto, pk=pk)
    puede_editar = request.user.has_perm("products.change_producto")
    # El costo guardado (no el que trae un POST con errores): contra él se
    # decide en pantalla si el costo cambió.
    costo_guardado = producto.precio_costo

    if request.method == "POST":
        producto_form = PreciosBaseProductoForm(
            request.POST, instance=producto, prefix="producto", puede_editar=puede_editar,
        )
        formset = ProductoPrecioFormSet(request.POST, instance=producto, prefix="precios")
        # Se validan los dos para mostrar todos los errores de una vez.
        validos = [producto_form.is_valid(), formset.is_valid()]
        if all(validos):
            try:
                with transaction.atomic():
                    if puede_editar and producto_form.has_changed():
                        producto.recalcular_precios_lista = False
                        producto_form.save()
                    formset.save()
                    producto.sincronizar_precio_venta_con_publico()
            except IntegrityError:
                messages.error(
                    request,
                    "No fue posible guardar: hay una lista de precios/sucursal repetida entre las filas.",
                )
            else:
                messages.success(request, "Precios del producto actualizados correctamente.")
                return redirect("products:product-list")
    else:
        producto_form = PreciosBaseProductoForm(instance=producto, prefix="producto", puede_editar=puede_editar)
        formset = ProductoPrecioFormSet(instance=producto, prefix="precios")

    return render(
        request,
        "products/producto_precios_form.html",
        {
            "producto": producto,
            "producto_form": producto_form,
            "formset": formset,
            "puede_editar_producto": puede_editar,
            "costo_guardado": costo_guardado,
            "active_module": "products",
        },
    )
