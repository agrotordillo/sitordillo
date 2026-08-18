from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento, seleccionar_lotes_para_salida

from .models import VentaDetalleLote


def validar_stock_disponible(almacen, lineas):
    """Pre-valida (sin mutar nada) que haya stock suficiente para todas las
    líneas. `lineas` es un iterable de (producto, cantidad, estrategia).
    Devuelve una lista de mensajes de error; vacía si todo está disponible.
    """
    errores = []
    for producto, cantidad, estrategia in lineas:
        try:
            seleccionar_lotes_para_salida(producto, almacen, cantidad, estrategia=estrategia)
        except ValueError as e:
            errores.append(str(e))
    return errores


@transaction.atomic
def procesar_lineas_venta(venta):
    """Descuenta inventario (FIFO/FEFO) por cada línea de la venta y deja
    registro de qué lote(s) surtieron cada línea, para poder costear
    correctamente una eventual devolución."""
    for detalle in venta.detalles.select_related("producto"):
        plan = seleccionar_lotes_para_salida(
            detalle.producto, venta.almacen, detalle.cantidad, estrategia=detalle.estrategia_salida
        )
        for lote, cantidad in plan:
            registrar_movimiento(
                lote,
                MovimientoInventario.Tipo.SALIDA,
                -cantidad,
                motivo=f"Venta {venta.folio}",
            )
            VentaDetalleLote.objects.create(
                detalle=detalle,
                lote=lote,
                cantidad=cantidad,
                costo_unitario=lote.costo_unitario,
            )


@transaction.atomic
def registrar_devolucion(devolucion):
    for detalle in devolucion.detalles.select_related("venta_detalle__producto"):
        if not detalle.reingresa_a_inventario:
            continue

        venta_detalle = detalle.venta_detalle
        lotes_origen = list(venta_detalle.lotes.all())
        cantidad_vendida = sum((l.cantidad for l in lotes_origen), Decimal("0.00"))
        if cantidad_vendida > 0:
            costo_promedio = sum(
                (l.cantidad * l.costo_unitario for l in lotes_origen), Decimal("0.00")
            ) / cantidad_vendida
        else:
            costo_promedio = venta_detalle.precio_unitario

        nuevo_lote = Lote(
            producto=venta_detalle.producto,
            almacen=devolucion.venta.almacen,
            fecha_ingreso=timezone.localdate(),
            costo_unitario=costo_promedio,
            cantidad_inicial=detalle.cantidad,
            cantidad_disponible=Decimal("0.00"),
        )
        nuevo_lote.full_clean()
        nuevo_lote.save()
        registrar_movimiento(
            nuevo_lote,
            MovimientoInventario.Tipo.DEVOLUCION,
            detalle.cantidad,
            motivo=f"Devolución {devolucion.folio} de {devolucion.venta.folio}",
        )
    return devolucion
