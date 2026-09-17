from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventario.models import Lote, MovimientoInventario
from apps.inventario.services import registrar_movimiento, seleccionar_lotes_para_salida
from apps.products.models import Producto, Turno

from .models import VentaDetalleLote


def validar_venta_a_credito(cliente, forma_pago, monto):
    """Si la venta es a crédito (forma de pago con clave SAT "99 - Por
    definir", ver Venta.CLAVE_CREDITO), valida que el cliente tenga
    crédito autorizado y que esta venta no lo deje por encima de su
    límite. No aplica a ninguna otra forma de pago -esas se asumen
    cobradas de inmediato-, ni cuando el cobro se dividió en varias formas
    de pago (forma_pago None: un pago dividido siempre es dinero ya
    recibido, nunca a crédito). Devuelve un mensaje de error, o None si no
    aplica o todo está en orden."""
    if forma_pago is None or forma_pago.clave != "99":
        return None
    if not cliente.tiene_credito:
        return (
            f'"{cliente.display_name}" no tiene crédito autorizado; no se le puede vender '
            'con forma de pago "Por definir".'
        )
    from apps.cobros.services import validar_limite_credito_cliente
    return validar_limite_credito_cliente(cliente, monto)


def validar_pago_dividido(total, montos):
    """Valida que el desglose de un cobro dividido en varias formas de
    pago cuadre EXACTO contra el total de la venta -no se ajusta ni se
    promedia nada: si no cuadra, se regresa el error para que el cajero
    corrija las cantidades a mano-. Mismo criterio que
    gastos.services.validar_distribucion para un reparto exacto."""
    errores = []
    montos = [m for m in montos if m is not None]
    if not montos:
        errores.append("Agrega al menos una forma de pago para dividir el cobro.")
        return errores

    suma = sum(montos, Decimal("0.00"))
    if suma != total:
        diferencia = total - suma
        if diferencia > 0:
            detalle = f"faltan ${diferencia} por cobrar"
        else:
            detalle = f"sobran ${-diferencia} asignados de más"
        errores.append(
            f"La suma de las formas de pago (${suma}) debe ser exactamente igual al total de la venta "
            f"(${total}): {detalle}."
        )
    return errores


def validar_turno_abierto(almacen, usuario):
    """Una venta solo se puede registrar si el usuario que la captura tiene
    ÉL MISMO un turno abierto en alguna caja (PuntoVenta tipo Cobro) de
    esa sucursal (ver products.Turno) -no basta con que la sucursal tenga
    alguno abierto por otra persona-, para que quede claro quién estuvo a
    cargo de esa operación. Una sucursal puede tener varias cajas, cada
    una con su propio turno abierto simultáneo (aunque hoy en la práctica
    solo se use una), así que esto no bloquea a un segundo cajero con su
    propia caja abierta. Devuelve un mensaje de error, o None si el
    usuario tiene un turno propio abierto en alguna caja de esa sucursal."""
    if not Turno.objects.filter(
        punto_venta__almacen=almacen, usuario=usuario, estatus=Turno.Estatus.ABIERTO
    ).exists():
        return f'No tienes un turno abierto en "{almacen.nombre}". Ábrelo antes de registrar la venta.'
    return None


def obtener_turno_abierto(almacen, usuario):
    """El turno propio y abierto de `usuario` en alguna caja de `almacen`
    -mismo criterio que validar_turno_abierto-, para dejarlo guardado en
    la Venta (ver Venta.turno) y así poder imprimir en el ticket con qué
    caja y bajo qué turno se cobró. Se llama siempre después de que
    validar_turno_abierto ya confirmó que existe uno; si por una
    condición de carrera ya no lo hay, regresa None."""
    return Turno.objects.filter(
        punto_venta__almacen=almacen, usuario=usuario, estatus=Turno.Estatus.ABIERTO
    ).select_related("punto_venta").first()


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
