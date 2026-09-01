from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.inventario.forms import RecepcionFormSet
from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento


def recepcion_compra_view(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    pendientes = list(
        orden.detalles.filter(cantidad_recibida__lt=F("cantidad")).select_related("producto")
    )

    if orden.estatus == OrdenCompra.Estatus.CANCELADA:
        messages.error(request, "No se puede recibir mercancía de una orden cancelada.")
        return redirect("compras:orden-list")

    if not pendientes:
        messages.info(request, "Esta orden de compra ya fue recibida por completo.")
        return redirect("compras:orden-list")

    detalles_por_id = {d.id: d for d in pendientes}

    if request.method == "POST":
        formset = RecepcionFormSet(request.POST)
        if formset.is_valid():
            hubo_error = False
            for form in formset:
                cantidad = form.cleaned_data["cantidad_recibir"]
                detalle = detalles_por_id.get(form.cleaned_data["detalle_id"])
                if detalle is None:
                    form.add_error(None, "Esta línea ya no pertenece a la orden.")
                    hubo_error = True
                    continue
                pendiente = detalle.cantidad - detalle.cantidad_recibida
                if cantidad > pendiente:
                    form.add_error(
                        "cantidad_recibir",
                        f"No puede recibir más de lo pendiente ({pendiente}).",
                    )
                    hubo_error = True

            if not hubo_error:
                with transaction.atomic():
                    for form in formset:
                        cantidad = form.cleaned_data["cantidad_recibir"]
                        if not cantidad:
                            continue
                        detalle = OrdenCompraDetalle.objects.select_for_update().get(
                            pk=form.cleaned_data["detalle_id"], orden_compra=orden
                        )
                        # cantidad_disponible arranca en 0: registrar_movimiento()
                        # es quien la eleva a `cantidad` vía el movimiento de
                        # ENTRADA, para que el ledger sea la única fuente de verdad.
                        lote = Lote(
                            producto=detalle.producto,
                            almacen=form.cleaned_data["almacen"],
                            orden_compra_detalle=detalle,
                            numero_lote=form.cleaned_data.get("numero_lote", ""),
                            fecha_ingreso=timezone.localdate(),
                            fecha_caducidad=form.cleaned_data.get("fecha_caducidad"),
                            costo_unitario=form.cleaned_data["costo_unitario"],
                            cantidad_inicial=cantidad,
                            cantidad_disponible=Decimal("0.00"),
                        )
                        lote.full_clean()
                        lote.save()
                        registrar_movimiento(
                            lote,
                            MovimientoInventario.Tipo.ENTRADA,
                            cantidad,
                            motivo=f"Recepción {orden.folio}",
                        )
                        detalle.cantidad_recibida = detalle.cantidad_recibida + cantidad
                        detalle.full_clean()
                        detalle.save()

                    detalles_actualizados = list(orden.detalles.all())
                    if all(d.cantidad_recibida >= d.cantidad for d in detalles_actualizados):
                        orden.estatus = OrdenCompra.Estatus.RECIBIDA
                    elif any(d.cantidad_recibida > 0 for d in detalles_actualizados):
                        orden.estatus = OrdenCompra.Estatus.PARCIAL
                    orden.save(update_fields=["estatus", "updated_at", "updated_by"])

                messages.success(request, "Recepción registrada correctamente.")
                return redirect("compras:orden-list")
    else:
        initial = [
            {
                "detalle_id": d.id,
                "cantidad_recibir": d.cantidad - d.cantidad_recibida,
                # precio_neto (no precio_unitario bruto): descuenta solo el %
                # base del proveedor (Proveedor.descuento), nunca el %
                # combinado/adicional de la orden — ver OrdenCompraDetalle.precio_neto.
                "costo_unitario": d.precio_neto,
                "almacen": orden.almacen_destino_id,
            }
            for d in pendientes
        ]
        formset = RecepcionFormSet(initial=initial)

    filas = list(zip(formset.forms, pendientes))
    return render(
        request,
        "inventario/recepcion_form.html",
        {"orden": orden, "formset": formset, "filas": filas, "active_module": "purchases"},
    )
