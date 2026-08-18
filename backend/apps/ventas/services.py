from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento, seleccionar_lotes_para_salida
from apps.products.models import Producto

from .models import VentaDetalleLote


def expandir_linea(producto, cantidad, estrategia):
    """Convierte una línea de venta en las líneas de producto real que
    afectan inventario. Para un producto normal, es la misma línea sin
    cambios. Para un paquete/combo, se expande en cada componente con su
    cantidad multiplicada (cantidad_componente_por_paquete * cantidad
    de paquetes vendidos)."""
    if producto.tipo == Producto.TipoProducto.PAQUETE:
        for componente in producto.componentes.select_related("producto_componente"):
            cantidad_componente = (componente.cantidad * cantidad).quantize(Decimal("0.01"))
            yield from expandir_linea(componente.producto_componente, cantidad_componente, estrategia)
    else:
        yield (producto, cantidad, estrategia)


def _error_paquete_sucursal(producto, almacen):
    """Un paquete lo arma y lo vende una sucursal específica (oferta y
    demanda locales); no lo puede vender otra sucursal aunque tenga los
    componentes en stock. Devuelve el mensaje de error, o None si aplica."""
    if producto.tipo == Producto.TipoProducto.PAQUETE and producto.almacen_id != almacen.id:
        return f"El paquete '{producto.nombre}' pertenece a la sucursal {producto.almacen.nombre} y no se puede vender aquí."
    return None


def validar_stock_disponible(almacen, lineas):
    """Pre-valida (sin mutar nada) que haya stock suficiente para todas las
    líneas. `lineas` es un iterable de (producto, cantidad, estrategia);
    los paquetes se expanden a sus componentes reales antes de validar.
    Devuelve una lista de mensajes de error; vacía si todo está disponible.
    """
    errores = []
    for producto, cantidad, estrategia in lineas:
        error_paquete = _error_paquete_sucursal(producto, almacen)
        if error_paquete:
            errores.append(error_paquete)
            continue
        for producto_real, cantidad_real, estrategia_real in expandir_linea(producto, cantidad, estrategia):
            try:
                seleccionar_lotes_para_salida(producto_real, almacen, cantidad_real, estrategia=estrategia_real)
            except ValueError as e:
                errores.append(str(e))
    return errores


@transaction.atomic
def procesar_lineas_venta(venta):
    """Descuenta inventario (FIFO/FEFO) por cada línea de la venta y deja
    registro de qué lote(s) surtieron cada línea, para poder costear
    correctamente una eventual devolución. Si la línea es un paquete, se
    descuenta cada componente por separado, pero todos los movimientos
    quedan ligados al mismo VentaDetalle (la línea que ve el cliente)."""
    for detalle in venta.detalles.select_related("producto"):
        error_paquete = _error_paquete_sucursal(detalle.producto, venta.almacen)
        if error_paquete:
            raise ValueError(error_paquete)
        for producto_real, cantidad_real, estrategia_real in expandir_linea(
            detalle.producto, detalle.cantidad, detalle.estrategia_salida
        ):
            plan = seleccionar_lotes_para_salida(
                producto_real, venta.almacen, cantidad_real, estrategia=estrategia_real
            )
            es_componente = producto_real.pk != detalle.producto_id
            motivo = f"Venta {venta.folio}"
            if es_componente:
                motivo += f" (componente de paquete: {detalle.producto.nombre})"
            for lote, cantidad in plan:
                registrar_movimiento(
                    lote,
                    MovimientoInventario.Tipo.SALIDA,
                    -cantidad,
                    motivo=motivo,
                )
                VentaDetalleLote.objects.create(
                    detalle=detalle,
                    lote=lote,
                    cantidad=cantidad,
                    costo_unitario=lote.costo_unitario,
                )


@transaction.atomic
def registrar_devolucion(devolucion):
    """Reingresa a inventario lo devuelto. Si la línea original era un
    paquete, se reconstruye un lote nuevo por cada componente distinto
    (con su propio costo promedio), no uno solo para el "paquete"."""
    for detalle in devolucion.detalles.select_related("venta_detalle__producto"):
        if not detalle.reingresa_a_inventario:
            continue

        venta_detalle = detalle.venta_detalle
        for producto_real, cantidad_real, _ in expandir_linea(
            venta_detalle.producto, detalle.cantidad, venta_detalle.estrategia_salida
        ):
            lotes_del_componente = list(venta_detalle.lotes.filter(lote__producto=producto_real))
            cantidad_vendida = sum((l.cantidad for l in lotes_del_componente), Decimal("0.00"))
            if cantidad_vendida > 0:
                costo_promedio = sum(
                    (l.cantidad * l.costo_unitario for l in lotes_del_componente), Decimal("0.00")
                ) / cantidad_vendida
            else:
                costo_promedio = producto_real.precio_costo

            nuevo_lote = Lote(
                producto=producto_real,
                almacen=devolucion.venta.almacen,
                fecha_ingreso=timezone.localdate(),
                costo_unitario=costo_promedio,
                cantidad_inicial=cantidad_real,
                cantidad_disponible=Decimal("0.00"),
            )
            nuevo_lote.full_clean()
            nuevo_lote.save()
            registrar_movimiento(
                nuevo_lote,
                MovimientoInventario.Tipo.DEVOLUCION,
                cantidad_real,
                motivo=f"Devolución {devolucion.folio} de {devolucion.venta.folio}",
            )
    return devolucion
