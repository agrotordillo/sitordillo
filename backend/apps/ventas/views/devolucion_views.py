from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView

from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.scoping import almacenes_visibles
from apps.ventas.models import DevolucionCliente, DevolucionClienteDetalle, Venta
from apps.ventas.forms import DevolucionFormSet
from apps.ventas.services import registrar_devolucion


class DevolucionClienteListView(PermissionRequiredMixin, ListView):
    permission_required = "ventas.view_devolucioncliente"
    model = DevolucionCliente
    template_name = "ventas/devolucion_list.html"
    context_object_name = "devoluciones"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        queryset = super().get_queryset().select_related("venta", "venta__cliente")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(venta__almacen__in=visibles)
        return queryset


@permission_required("ventas.add_devolucioncliente", raise_exception=True)
def devolucion_cliente_view(request, pk):
    ventas_qs = Venta.objects.all()
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        ventas_qs = ventas_qs.filter(almacen__in=visibles)
    venta = get_object_or_404(ventas_qs, pk=pk)

    # Doble clic o recarga de una devolución que ya se guardó (ver
    # apps.core.envio_unico).
    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

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
                try:
                    with transaction.atomic():
                        envio = reservar_envio(request)
                        # Con la venta bloqueada, lo pendiente de devolver que
                        # revisa DevolucionClienteDetalle.clean() es el vigente:
                        # dos devoluciones simultáneas no rebasan lo vendido.
                        Venta.objects.select_for_update().get(pk=venta.pk)
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
                        envio.completar(reverse("ventas:venta-list"))
                except EnvioDuplicado as duplicado:
                    return respuesta_envio_duplicado(request, duplicado.url_resultado, "ventas:venta-list")
                except ERRORES_DE_NEGOCIO as e:
                    # La transacción ya se revirtió: no queda ni la
                    # devolución ni ningún lote a medias.
                    for mensaje in mensajes_de_error(e):
                        messages.error(request, mensaje)
                else:
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
