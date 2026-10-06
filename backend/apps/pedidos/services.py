from django.db import transaction
from django.utils import timezone

from apps.inventario.models import MovimientoInventario
from apps.inventario.services import (
    bloquear_existencias,
    bloquear_lotes,
    registrar_movimiento,
    seleccionar_lotes_para_salida,
)
from apps.products.services import resolver_lista_precio_cliente, resolver_precio_linea
from apps.ventas.models import VentaDetalle, VentaDetalleLote
from apps.ventas.services import expandir_linea, validar_stock_disponible

from .models import Pedido, PedidoDetalleLote


class StockInsuficiente(ValueError):
    """No alcanza la existencia de la sucursal para apartar el pedido.
    Trae la lista completa de faltantes (uno por producto, ver
    ventas.services.validar_stock_disponible) para que mostrador vea de una
    vez todo lo que falta, no un producto a la vez."""

    def __init__(self, errores):
        self.errores = errores
        super().__init__(" ".join(errores))


def bloquear_pedido_abierto(pedido):
    """Vuelve a leer el pedido con la fila bloqueada y confirma que siga
    abierto: dos cajas (o caja y mostrador) actuando sobre el mismo pedido
    al mismo tiempo no deben poder convertirlo y cancelarlo a la vez, ni
    convertirlo dos veces."""
    bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if bloqueado.estatus != Pedido.Estatus.ABIERTO:
        raise ValueError(
            f"El pedido {bloqueado.numero_documento} ya está {bloqueado.get_estatus_display().lower()}."
        )
    return bloqueado


@transaction.atomic
def apartar_inventario(pedido):
    """El "traspaso temporal" del pedido: descuenta de los lotes de la
    sucursal (FIFO/FEFO, mismo criterio y misma expansión de paquetes que
    una venta, ver ventas.services.procesar_lineas_venta) con un
    movimiento tipo PEDIDO, y deja en PedidoDetalleLote de qué lote salió
    cada cantidad para poder regresarla exactamente ahí (cancelación) o
    pasarla tal cual a la venta (conversión).

    Lanza StockInsuficiente si algo no alcanza; como corre dentro de una
    transacción, nada de lo ya apartado en esta llamada queda aplicado."""
    detalles = list(pedido.detalles.select_related("producto"))
    salidas = [
        (detalle, producto_real, cantidad_real, estrategia_real)
        for detalle in detalles
        for producto_real, cantidad_real, estrategia_real in expandir_linea(
            detalle.producto, detalle.cantidad, detalle.estrategia_salida
        )
    ]
    # Lotes bloqueados antes de validar: la existencia que se revisa es la
    # misma que se aparta, sin que otra venta o pedido la tome a la mitad.
    bloquear_existencias(pedido.almacen, [producto_real for _, producto_real, _, _ in salidas])
    errores = validar_stock_disponible(
        pedido.almacen, [(d.producto, d.cantidad, d.estrategia_salida) for d in detalles],
    )
    if errores:
        raise StockInsuficiente(errores)

    for detalle, producto_real, cantidad_real, estrategia_real in salidas:
        plan = seleccionar_lotes_para_salida(
            producto_real, pedido.almacen, cantidad_real, estrategia=estrategia_real
        )
        motivo = f"Pedido {pedido.numero_documento}"
        if producto_real.pk != detalle.producto_id:
            motivo += f" (componente de paquete: {detalle.producto.nombre})"
        for lote, cantidad in plan:
            registrar_movimiento(lote, MovimientoInventario.Tipo.PEDIDO, -cantidad, motivo=motivo)
            PedidoDetalleLote.objects.create(
                detalle=detalle,
                lote=lote,
                cantidad=cantidad,
                costo_unitario=lote.costo_unitario,
            )


@transaction.atomic
def liberar_inventario(pedido, motivo):
    """Regresa a sus lotes de origen todo lo que el pedido tiene apartado
    y borra el registro del apartado. Se usa al cancelar y al editar un
    pedido abierto (se libera todo y se vuelve a apartar con las líneas
    nuevas)."""
    apartados = list(PedidoDetalleLote.objects.filter(detalle__pedido=pedido).select_related("lote"))
    bloquear_lotes([apartado.lote_id for apartado in apartados])
    for apartado in apartados:
        registrar_movimiento(apartado.lote, MovimientoInventario.Tipo.PEDIDO, apartado.cantidad, motivo=motivo)
    PedidoDetalleLote.objects.filter(pk__in=[apartado.pk for apartado in apartados]).delete()


@transaction.atomic
def cancelar_pedido(pedido, motivo=""):
    pedido = bloquear_pedido_abierto(pedido)
    liberar_inventario(pedido, motivo=f"Cancelación de pedido {pedido.numero_documento}")
    pedido.estatus = Pedido.Estatus.CANCELADO
    pedido.fecha_cancelacion = timezone.now()
    pedido.motivo_cancelacion = motivo
    pedido.save(update_fields=[
        "estatus", "fecha_cancelacion", "motivo_cancelacion", "updated_at", "updated_by",
    ])
    return pedido


@transaction.atomic
def convertir_pedido_a_venta(pedido, venta):
    """Pasa las líneas del pedido, tal cual (mismos productos y cantidades),
    a `venta` -ya guardada, sin detalles todavía-. La mercancía no se
    vuelve a planear por FIFO: se toma de los MISMOS lotes que el pedido
    tenía apartados, registrando en cada uno la liberación del apartado y
    enseguida la SALIDA de la venta (así el kardex y el análisis de
    "última venta" la siguen viendo como venta), y copiando lote y costo a
    VentaDetalleLote para que una devolución posterior se costee igual que
    cualquier otra venta.

    El precio sí se vuelve a resolver aquí con el cliente y la sucursal de
    la venta, igual que al convertir una cotización -nunca se copia el
    precio_unitario guardado en el pedido-."""
    pedido = bloquear_pedido_abierto(pedido)
    if venta.almacen_id != pedido.almacen_id:
        raise ValueError("La venta debe registrarse en la misma sucursal del pedido.")
    bloquear_lotes(
        PedidoDetalleLote.objects.filter(detalle__pedido=pedido).values_list("lote_id", flat=True)
    )

    lista_precio = resolver_lista_precio_cliente(venta.cliente)
    for detalle in pedido.detalles.select_related("producto").prefetch_related("lotes__lote__producto"):
        precio_unitario, lista_linea = resolver_precio_linea(detalle.producto, lista_precio, venta.almacen)
        venta_detalle = VentaDetalle.objects.create(
            venta=venta,
            producto=detalle.producto,
            cantidad=detalle.cantidad,
            precio_unitario=precio_unitario,
            lista_precio=lista_linea,
            estrategia_salida=VentaDetalle.Estrategia.FIFO,
        )
        for apartado in detalle.lotes.all():
            motivo_venta = f"Venta {venta.folio} (pedido {pedido.numero_documento})"
            if apartado.lote.producto_id != detalle.producto_id:
                motivo_venta += f" (componente de paquete: {detalle.producto.nombre})"
            registrar_movimiento(
                apartado.lote,
                MovimientoInventario.Tipo.PEDIDO,
                apartado.cantidad,
                motivo=f"Pedido {pedido.numero_documento} entregado en venta {venta.folio}",
            )
            registrar_movimiento(
                apartado.lote, MovimientoInventario.Tipo.SALIDA, -apartado.cantidad, motivo=motivo_venta,
            )
            VentaDetalleLote.objects.create(
                detalle=venta_detalle,
                lote=apartado.lote,
                cantidad=apartado.cantidad,
                costo_unitario=apartado.costo_unitario,
            )

    pedido.venta = venta
    pedido.estatus = Pedido.Estatus.CONVERTIDO
    pedido.save(update_fields=["venta", "estatus", "updated_at", "updated_by"])
    return pedido
