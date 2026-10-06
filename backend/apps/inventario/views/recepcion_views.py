from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.inventario.forms import RecepcionFormSet
from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento


# Compras recibe el producto contra la factura/nota del proveedor; Almacén
# resguarda el inventario físico y por eso también puede darle entrada.
# Cualquier incidencia detectada en la recepción física se reporta a
# Compras para su seguimiento.
class _ExcedePendiente(Exception):
    """Otra recepción simultánea ya recibió parte de lo que este formulario
    quería recibir de una línea."""

    def __init__(self, form, pendiente):
        super().__init__()
        self.form = form
        self.pendiente = pendiente


def _mensaje_no_admite_recepcion(orden):
    if orden.estatus == OrdenCompra.Estatus.CANCELADA:
        return "No se puede recibir mercancía de una orden cancelada."
    return (
        f"La orden {orden.folio} sigue en {orden.get_estatus_display()}: márcala como Enviada "
        "antes de recibir mercancía."
    )


@permission_required("inventario.add_lote", raise_exception=True)
def recepcion_compra_view(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)

    # Doble clic o recarga de una recepción que ya se guardó (ver
    # apps.core.envio_unico).
    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    pendientes = list(
        orden.detalles.filter(cantidad_recibida__lt=F("cantidad")).select_related("producto")
    )

    if not orden.admite_recepcion:
        messages.error(request, _mensaje_no_admite_recepcion(orden))
        return redirect("compras:orden-list")

    if not pendientes:
        messages.info(request, "Esta orden de compra ya fue recibida por completo.")
        return redirect("compras:orden-list")

    detalles_por_id = {d.id: d for d in pendientes}

    if request.method == "POST":
        formset = RecepcionFormSet(request.POST, form_kwargs={"user": request.user})
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
                try:
                    with transaction.atomic():
                        envio = reservar_envio(request)
                        _recibir(orden, formset)
                        envio.completar(reverse("compras:orden-list"))
                except EnvioDuplicado as duplicado:
                    return respuesta_envio_duplicado(request, duplicado.url_resultado, "compras:orden-list")
                except _ExcedePendiente as e:
                    e.form.add_error(
                        "cantidad_recibir",
                        f"Otra recepción se registró mientras capturabas: ya solo quedan {e.pendiente} pendientes.",
                    )
                except ERRORES_DE_NEGOCIO as e:
                    for mensaje in mensajes_de_error(e):
                        messages.error(request, mensaje)
                else:
                    messages.success(request, "Recepción registrada correctamente.")
                    return redirect("compras:orden-list")
    else:
        initial = [
            {
                "detalle_id": d.id,
                "cantidad_recibir": d.cantidad - d.cantidad_recibida,
                # costo_con_flete = precio_neto (descuenta solo el % base del
                # proveedor, nunca el % combinado/adicional de la orden) más
                # el flete de la orden prorrateado a este renglón — ver
                # OrdenCompraDetalle.precio_neto y .flete_unitario.
                "costo_unitario": d.costo_con_flete,
                "almacen": orden.almacen_destino_id,
            }
            for d in pendientes
        ]
        formset = RecepcionFormSet(initial=initial, form_kwargs={"user": request.user})

    filas = list(zip(formset.forms, pendientes))
    return render(
        request,
        "inventario/recepcion_form.html",
        {"orden": orden, "formset": formset, "filas": filas, "active_module": "purchases"},
    )


def _recibir(orden, formset):
    """Da de alta la mercancía recibida con la orden y cada línea bloqueadas,
    revalidando lo pendiente ya bajo el bloqueo: dos recepciones simultáneas
    de la misma orden no pueden recibir de más (B18 en docs/AUDITORIA.md).
    Debe llamarse dentro de una transacción."""
    orden = OrdenCompra.objects.select_for_update().get(pk=orden.pk)
    if not orden.admite_recepcion:
        raise ValueError(f"Mientras capturabas la recepción: {_mensaje_no_admite_recepcion(orden)}")

    for form in formset:
        cantidad = form.cleaned_data["cantidad_recibir"]
        if not cantidad:
            continue
        detalle = OrdenCompraDetalle.objects.select_for_update().get(
            pk=form.cleaned_data["detalle_id"], orden_compra=orden
        )
        pendiente = detalle.cantidad - detalle.cantidad_recibida
        if cantidad > pendiente:
            raise _ExcedePendiente(form, pendiente)

        # cantidad_disponible arranca en 0: registrar_movimiento() es quien
        # la eleva a `cantidad` vía el movimiento de ENTRADA, para que el
        # ledger sea la única fuente de verdad.
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

    orden.actualizar_estatus_por_recepcion()
