from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.inventario.models import DOS_DECIMALES, Lote, MovimientoInventario, redondear_costo
from apps.inventario.services import bloquear_existencias, registrar_movimiento, seleccionar_lotes_para_salida
from apps.products.models import Producto

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


def validar_efectivo_recibido(venta):
    """Lo que entregó el cliente en efectivo debe cubrir el total -si no, el
    ticket mostraría un "cambio" negativo-. Se llama con los detalles ya
    guardados, cuando venta.total ya es el real. La usan por igual la venta
    directa y la conversión de cotización o pedido (B19 en
    docs/AUDITORIA.md). Lanza ValueError."""
    if venta.efectivo_recibido is not None and venta.efectivo_recibido < venta.total:
        raise ValueError(
            f"El efectivo recibido (${venta.efectivo_recibido}) no puede ser menor que el total de la venta "
            f"(${venta.total})."
        )


def resumen_turno(turno):
    """Corte de caja de un turno: total vendido y desglose por forma de
    pago -incluyendo el de cada venta con cobro dividido, que no tiene
    `forma_pago` propio y se reparte entre sus VentaPago-, más cuáles de
    sus ventas a Público en general siguen sin facturar (candidatas a la
    factura global de ese turno, ver facturacion.factura_service)."""
    from apps.clientes.models import Cliente

    ventas = list(
        turno.ventas.select_related("forma_pago", "factura").prefetch_related("pagos__forma_pago")
    )

    por_forma_pago = {}
    for venta in ventas:
        if venta.pago_dividido:
            for pago in venta.pagos.all():
                clave = pago.forma_pago.descripcion
                por_forma_pago[clave] = por_forma_pago.get(clave, Decimal("0.00")) + pago.monto
        else:
            clave = venta.forma_pago.descripcion
            por_forma_pago[clave] = por_forma_pago.get(clave, Decimal("0.00")) + venta.total

    publico = Cliente.publico_general()
    pendientes_global = [
        v for v in ventas
        if publico is not None and v.cliente_id == publico.id and not v.es_remision
        and not hasattr(v, "factura") and v.factura_global_id is None
    ]

    return {
        "ventas": ventas,
        "total_ventas": len(ventas),
        "total_vendido": sum((v.total for v in ventas), Decimal("0.00")),
        "por_forma_pago": por_forma_pago,
        "pendientes_factura_global": pendientes_global,
    }


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


def expandir_linea(producto, cantidad, estrategia):
    """Convierte una línea de venta en las líneas de producto real que
    afectan inventario. Para un producto normal, es la misma línea sin
    cambios. Para un paquete/combo con existencia propia (se armó con
    anticipación, ver apps.inventario.services.registrar_ensamble_paquete),
    se vende directo de ahí, sin tocar los componentes de nuevo. Si no
    tiene existencia propia, se expande en cada componente con su cantidad
    multiplicada (cantidad_componente_por_paquete * cantidad de paquetes
    vendidos) -el paquete "virtual" de siempre, armado al momento de
    vender."""
    if producto.tipo == Producto.TipoProducto.PAQUETE:
        tiene_existencia_propia = Lote.objects.filter(
            producto=producto, almacen_id=producto.almacen_id, is_active=True, cantidad_disponible__gt=0
        ).exists()
        if tiene_existencia_propia:
            yield (producto, cantidad, estrategia)
            return
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
    quedan ligados al mismo VentaDetalle (la línea que ve el cliente).

    Primero se expanden todas las líneas y se bloquean de una vez los lotes
    de todos los productos reales (ver inventario.services.
    bloquear_existencias): el plan FIFO de cada línea se arma ya con las
    existencias vigentes y ninguna otra venta simultánea las puede tomar."""
    salidas = []
    for detalle in venta.detalles.select_related("producto"):
        error_paquete = _error_paquete_sucursal(detalle.producto, venta.almacen)
        if error_paquete:
            raise ValueError(error_paquete)
        for producto_real, cantidad_real, estrategia_real in expandir_linea(
            detalle.producto, detalle.cantidad, detalle.estrategia_salida
        ):
            salidas.append((detalle, producto_real, cantidad_real, estrategia_real))
    bloquear_existencias(venta.almacen, [producto_real for _, producto_real, _, _ in salidas])

    for detalle, producto_real, cantidad_real, estrategia_real in salidas:
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


@dataclass
class Reingreso:
    """Una entrada de inventario que genera una línea de devolución: qué
    producto real regresa, cuánto, a qué costo y con qué datos de lote."""

    producto: Producto
    cantidad: Decimal
    costo_unitario: Decimal
    numero_lote: str = ""
    fecha_caducidad: date | None = None


def _proporcion(cantidad_salida, devuelto, cantidad_linea):
    """Cuánto de `cantidad_salida` corresponde a haber devuelto `devuelto`
    de una línea de `cantidad_linea` unidades. Al devolver la línea completa
    regresa exacto lo que salió, sin residuos de redondeo."""
    if devuelto >= cantidad_linea:
        return cantidad_salida
    return (cantidad_salida * devuelto / cantidad_linea).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


def _reingresos_por_lotes_vendidos(detalle_devolucion, vendidos):
    """Reconstruye lo devuelto a partir de lo que REALMENTE salió en la
    venta (VentaDetalleLote), no de la receta actual del producto: si un
    paquete cambió de componentes, o hoy tiene existencia armada propia,
    regresa lo mismo que se entregó entonces. Por cada producto real se
    regresa la parte proporcional a lo devuelto de la línea, calculada como
    diferencia de acumulados (lo que corresponde a todo lo devuelto hasta
    ahora menos lo que correspondía a lo devuelto antes), para que varias
    devoluciones parciales de la misma línea sumen exacto lo que salió."""
    venta_detalle = detalle_devolucion.venta_detalle
    devuelto_antes = sum(
        (d.cantidad for d in venta_detalle.devoluciones.filter(pk__lt=detalle_devolucion.pk)),
        Decimal("0.00"),
    )
    devuelto_despues = devuelto_antes + detalle_devolucion.cantidad

    por_producto = {}
    for vendido in vendidos:
        grupo = por_producto.setdefault(
            vendido.lote.producto_id,
            {"producto": vendido.lote.producto, "cantidad": Decimal("0.00"), "valor": Decimal("0.00"), "lotes": []},
        )
        grupo["cantidad"] += vendido.cantidad
        grupo["valor"] += vendido.cantidad * vendido.costo_unitario
        grupo["lotes"].append(vendido.lote)

    reingresos = []
    for grupo in por_producto.values():
        cantidad = (
            _proporcion(grupo["cantidad"], devuelto_despues, venta_detalle.cantidad)
            - _proporcion(grupo["cantidad"], devuelto_antes, venta_detalle.cantidad)
        )
        if cantidad <= 0:
            continue
        numeros_lote = {lote.numero_lote for lote in grupo["lotes"]}
        caducidades = [lote.fecha_caducidad for lote in grupo["lotes"] if lote.fecha_caducidad]
        reingresos.append(Reingreso(
            producto=grupo["producto"],
            cantidad=cantidad,
            costo_unitario=redondear_costo(grupo["valor"] / grupo["cantidad"]),
            # Si salió de un solo número de lote se conserva; si salió de
            # varios no se sabe de cuál regresa.
            numero_lote=numeros_lote.pop() if len(numeros_lote) == 1 else "",
            # La caducidad más próxima de los lotes de origen: es la opción
            # segura, la mercancía sale primero (FEFO) y nunca se considera
            # vigente de más.
            fecha_caducidad=min(caducidades) if caducidades else None,
        ))
    return reingresos


def _reingresos_sin_registro_de_lotes(detalle_devolucion):
    """Respaldo para ventas sin VentaDetalleLote (registradas antes de que
    se guardara de qué lote salía cada línea): se expande la línea con la
    receta actual y se costea al costo de catálogo."""
    venta_detalle = detalle_devolucion.venta_detalle
    return [
        Reingreso(producto=producto, cantidad=cantidad, costo_unitario=redondear_costo(producto.precio_costo))
        for producto, cantidad, _ in expandir_linea(
            venta_detalle.producto, detalle_devolucion.cantidad, venta_detalle.estrategia_salida
        )
    ]


@transaction.atomic
def registrar_devolucion(devolucion):
    """Reingresa a inventario lo devuelto, en lotes nuevos de la sucursal
    de la venta: uno por cada producto real que salió en la línea (los
    componentes, si fue un paquete armado al vender), con el costo
    promedio con el que salió (ver _reingresos_por_lotes_vendidos). Las
    líneas marcadas para no reingresar no generan movimiento: esa
    mercancía ya había salido con la venta."""
    detalles = devolucion.detalles.select_related("venta_detalle__producto").prefetch_related(
        Prefetch("venta_detalle__lotes", queryset=VentaDetalleLote.objects.select_related("lote__producto"))
    )
    for detalle in detalles:
        if not detalle.reingresa_a_inventario:
            continue

        vendidos = list(detalle.venta_detalle.lotes.all())
        reingresos = (
            _reingresos_por_lotes_vendidos(detalle, vendidos) if vendidos
            else _reingresos_sin_registro_de_lotes(detalle)
        )
        for reingreso in reingresos:
            nuevo_lote = Lote(
                producto=reingreso.producto,
                almacen=devolucion.venta.almacen,
                numero_lote=reingreso.numero_lote,
                fecha_ingreso=timezone.localdate(),
                fecha_caducidad=reingreso.fecha_caducidad,
                costo_unitario=reingreso.costo_unitario,
                cantidad_inicial=reingreso.cantidad,
                cantidad_disponible=Decimal("0.00"),
            )
            nuevo_lote.full_clean()
            nuevo_lote.save()
            registrar_movimiento(
                nuevo_lote,
                MovimientoInventario.Tipo.DEVOLUCION,
                reingreso.cantidad,
                motivo=f"Devolución {devolucion.folio} de {devolucion.venta.folio}",
            )
    return devolucion
