from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from apps.ventas.models import DevolucionCliente, DevolucionClienteDetalle, Venta
from apps.ventas.forms import DevolucionFormSet
from apps.ventas.services import registrar_devolucion


class DevolucionClienteListView(ListView):
    model = DevolucionCliente
    template_name = "ventas/devolucion_list.html"
    context_object_name = "devoluciones"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("venta", "venta__cliente")


def devolucion_cliente_view(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    pendientes = [d for d in venta.detalles.select_related("producto") if d.cantidad_devuelta < d.cantidad]

    if not pendientes:
        messages.info(request, "Esta venta ya no tiene productos pendientes de devolución.")
        return redirect("ventas:venta-list")

    detalles_por_id = {d.id: d for d in pendientes}

    if request.method == "POST":
        formset = DevolucionFormSet(request.POST)
        if formset.is_valid():
            hubo_error = False
            for form in formset:
                cantidad = form.cleaned_data["cantidad"]
                detalle = detalles_por_id.get(form.cleaned_data["venta_detalle_id"])
                if detalle is None:
                    form.add_error(None, "Esta línea ya no pertenece a la venta.")
                    hubo_error = True
                    continue
                pendiente = detalle.cantidad - detalle.cantidad_devuelta
                if cantidad > pendiente:
                    form.add_error("cantidad", f"No puede devolver más de lo pendiente ({pendiente}).")
                    hubo_error = True

            if not hubo_error and not any(f.cleaned_data["cantidad"] for f in formset):
                messages.error(request, "Indica al menos una cantidad a devolver.")
                hubo_error = True

            if not hubo_error:
                with transaction.atomic():
                    devolucion = DevolucionCliente.objects.create(
                        venta=venta,
                        fecha=timezone.localdate(),
                        motivo=request.POST.get("motivo", ""),
                    )
                    for form in formset:
                        cantidad = form.cleaned_data["cantidad"]
                        if not cantidad:
                            continue
                        detalle = detalles_por_id[form.cleaned_data["venta_detalle_id"]]
                        linea = DevolucionClienteDetalle(
                            devolucion=devolucion,
                            venta_detalle=detalle,
                            cantidad=cantidad,
                            reingresa_a_inventario=form.cleaned_data["reingresa_a_inventario"],
                        )
                        linea.full_clean()
                        linea.save()
                    registrar_devolucion(devolucion)

                messages.success(request, "Devolución registrada correctamente.")
                return redirect("ventas:venta-list")
    else:
        initial = [{"venta_detalle_id": d.id, "cantidad": 0} for d in pendientes]
        formset = DevolucionFormSet(initial=initial)

    filas = list(zip(formset.forms, pendientes))
    return render(
        request,
        "ventas/devolucion_form.html",
        {"venta": venta, "formset": formset, "filas": filas, "active_module": "sales"},
    )
