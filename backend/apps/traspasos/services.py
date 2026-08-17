from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento, seleccionar_lotes_para_salida

from .models import Traspaso, TraspasoLote


@transaction.atomic
def enviar_traspaso(traspaso):
    if traspaso.estatus != Traspaso.Estatus.BORRADOR:
        raise ValueError("Solo se puede enviar un traspaso en borrador.")

    detalles = list(traspaso.detalles.select_related("producto"))
    if not detalles:
        raise ValueError("El traspaso no tiene productos que enviar.")

    for detalle in detalles:
        plan = seleccionar_lotes_para_salida(
            detalle.producto,
            traspaso.almacen_origen,
            detalle.cantidad,
            estrategia=detalle.estrategia_salida,
        )
        for lote_origen, cantidad in plan:
            registrar_movimiento(
                lote_origen,
                MovimientoInventario.Tipo.TRASPASO,
                -cantidad,
                motivo=f"Traspaso {traspaso.folio} a {traspaso.almacen_destino.nombre}",
            )
            TraspasoLote.objects.create(
                detalle=detalle,
                lote_origen=lote_origen,
                cantidad=cantidad,
            )

    traspaso.estatus = Traspaso.Estatus.ENVIADO
    traspaso.save(update_fields=["estatus", "updated_at", "updated_by"])
    return traspaso


@transaction.atomic
def recibir_traspaso(traspaso):
    if traspaso.estatus != Traspaso.Estatus.ENVIADO:
        raise ValueError("Solo se puede recibir un traspaso enviado.")

    pendientes = TraspasoLote.objects.filter(
        detalle__traspaso=traspaso, lote_destino__isnull=True
    ).select_related("lote_origen", "detalle__producto")

    if not pendientes:
        raise ValueError("No hay lotes pendientes de recibir en este traspaso.")

    for traspaso_lote in pendientes:
        origen = traspaso_lote.lote_origen
        nuevo_lote = Lote(
            producto=origen.producto,
            almacen=traspaso.almacen_destino,
            numero_lote=origen.numero_lote,
            fecha_ingreso=timezone.localdate(),
            fecha_caducidad=origen.fecha_caducidad,
            costo_unitario=origen.costo_unitario,
            cantidad_inicial=traspaso_lote.cantidad,
            cantidad_disponible=Decimal("0.00"),
        )
        nuevo_lote.full_clean()
        nuevo_lote.save()
        registrar_movimiento(
            nuevo_lote,
            MovimientoInventario.Tipo.TRASPASO,
            traspaso_lote.cantidad,
            motivo=f"Recepción de traspaso {traspaso.folio} desde {traspaso.almacen_origen.nombre}",
        )
        traspaso_lote.lote_destino = nuevo_lote
        traspaso_lote.save(update_fields=["lote_destino", "updated_at", "updated_by"])

    traspaso.estatus = Traspaso.Estatus.RECIBIDO
    traspaso.fecha_recepcion = timezone.localdate()
    traspaso.save(update_fields=["estatus", "fecha_recepcion", "updated_at", "updated_by"])
    return traspaso
