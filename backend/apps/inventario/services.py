from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import Lote, MovimientoInventario


@transaction.atomic
def registrar_movimiento(lote, tipo, cantidad, motivo=""):
    """Único punto de entrada para modificar Lote.cantidad_disponible.

    `cantidad` es un delta con signo (positivo para entradas, negativo para
    salidas/mermas). Bloquea el lote (select_for_update) para evitar
    condiciones de carrera si dos movimientos se registran en paralelo.
    """
    lote = Lote.objects.select_for_update().get(pk=lote.pk)
    cantidad_anterior = lote.cantidad_disponible
    cantidad_nueva = cantidad_anterior + cantidad

    movimiento = MovimientoInventario(
        lote=lote,
        tipo=tipo,
        cantidad=cantidad,
        cantidad_anterior=cantidad_anterior,
        cantidad_nueva=cantidad_nueva,
        motivo=motivo,
    )
    movimiento.full_clean()

    if cantidad_nueva < 0:
        raise ValueError(
            f"El movimiento dejaría el lote {lote} con cantidad disponible negativa ({cantidad_nueva})."
        )

    lote.cantidad_disponible = cantidad_nueva
    lote.full_clean()
    lote.save(update_fields=["cantidad_disponible", "updated_at", "updated_by"])
    movimiento.save()
    return movimiento


def seleccionar_lotes_para_salida(producto, almacen, cantidad_requerida, estrategia="fifo"):
    """Devuelve el plan [(lote, cantidad_a_tomar), ...] para cubrir `cantidad_requerida`.

    estrategia="fifo": primero los lotes que ingresaron antes (fecha_ingreso).
    estrategia="fefo": primero los que caducan antes (fecha_caducidad), dejando
    al final los que no tienen caducidad registrada; a igualdad de caducidad
    se desempata por FIFO.
    Lanza ValueError si el stock disponible no alcanza.
    """
    if cantidad_requerida <= 0:
        raise ValueError("La cantidad requerida debe ser mayor a cero.")

    # Solo lectura: el bloqueo real ocurre en registrar_movimiento() al ejecutar
    # el plan, así que esta función puede usarse también para previsualizar.
    lotes = Lote.objects.filter(
        producto=producto,
        almacen=almacen,
        is_active=True,
        cantidad_disponible__gt=0,
    )

    if estrategia == "fefo":
        lotes = lotes.order_by(models.F("fecha_caducidad").asc(nulls_last=True), "fecha_ingreso")
    elif estrategia == "fifo":
        lotes = lotes.order_by("fecha_ingreso", "created_at")
    else:
        raise ValueError(f"Estrategia de salida desconocida: {estrategia!r}")

    restante = cantidad_requerida
    plan = []
    for lote in lotes:
        if restante <= 0:
            break
        tomar = min(lote.cantidad_disponible, restante)
        plan.append((lote, tomar))
        restante -= tomar

    if restante > 0:
        raise ValueError(
            f"Stock insuficiente de {producto} en {almacen}: faltan {restante} unidades."
        )

    return plan


@transaction.atomic
def registrar_salida(producto, almacen, cantidad, estrategia="fifo", motivo=""):
    """Ejecuta el plan FIFO/FEFO y registra un movimiento de salida por cada lote afectado."""
    plan = seleccionar_lotes_para_salida(producto, almacen, cantidad, estrategia=estrategia)
    return [
        registrar_movimiento(lote, MovimientoInventario.Tipo.SALIDA, -tomar, motivo=motivo)
        for lote, tomar in plan
    ]


@transaction.atomic
def corregir_recepcion(lote_incorrecto, cantidad, producto_correcto, motivo=""):
    """Corrige una recepción donde se eligió el producto equivocado, para el
    caso en que nada del lote incorrecto se haya vendido/movido todavía: no
    revierte ventas, solo entradas de inventario.

    Anula `cantidad` del lote incorrecto (movimiento AJUSTE, nunca se edita
    cantidad_disponible directamente) y la traslada a un lote nuevo del
    producto correcto, en el mismo almacén, con el mismo costo/número de
    lote/caducidad (es la misma mercancía física, solo mal etiquetada).
    Ajusta cantidad_recibida en ambas líneas de la orden de compra —crea la
    línea del producto correcto si la orden no la tenía— y recalcula el
    estatus de la orden."""
    from apps.compras.models import OrdenCompraDetalle

    detalle_incorrecto = lote_incorrecto.orden_compra_detalle
    if detalle_incorrecto is None:
        raise ValueError(
            "Este lote no está ligado a una línea de orden de compra; no se puede corregir aquí."
        )
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad a corregir debe ser mayor a cero.")
    if cantidad > lote_incorrecto.cantidad_disponible:
        raise ValueError("No puedes corregir más de lo disponible en el lote.")

    motivo_final = motivo or f"Corrección: se recibió {producto_correcto.nombre} en su lugar"
    registrar_movimiento(lote_incorrecto, MovimientoInventario.Tipo.AJUSTE, -cantidad, motivo=motivo_final)
    # ver comentario más abajo sobre lote_nuevo.refresh_from_db(): mismo caso.
    lote_incorrecto.refresh_from_db()

    orden = detalle_incorrecto.orden_compra
    detalle_incorrecto.cantidad_recibida = max(
        Decimal("0.00"), detalle_incorrecto.cantidad_recibida - cantidad
    )
    detalle_incorrecto.full_clean()
    detalle_incorrecto.save(update_fields=["cantidad_recibida", "updated_at", "updated_by"])

    detalle_correcto = orden.detalles.filter(producto=producto_correcto).first()
    if detalle_correcto is None:
        detalle_correcto = OrdenCompraDetalle(
            orden_compra=orden,
            producto=producto_correcto,
            cantidad=cantidad,
            precio_unitario=detalle_incorrecto.precio_unitario,
            cantidad_recibida=Decimal("0.00"),
        )
    detalle_correcto.cantidad_recibida = (detalle_correcto.cantidad_recibida or Decimal("0.00")) + cantidad
    if detalle_correcto.cantidad_recibida > detalle_correcto.cantidad:
        detalle_correcto.cantidad = detalle_correcto.cantidad_recibida
    detalle_correcto.full_clean()
    detalle_correcto.save()

    lote_nuevo = Lote(
        producto=producto_correcto,
        almacen=lote_incorrecto.almacen,
        orden_compra_detalle=detalle_correcto,
        numero_lote=lote_incorrecto.numero_lote,
        fecha_ingreso=timezone.localdate(),
        fecha_caducidad=lote_incorrecto.fecha_caducidad,
        costo_unitario=lote_incorrecto.costo_unitario,
        cantidad_inicial=cantidad,
        cantidad_disponible=Decimal("0.00"),
    )
    lote_nuevo.full_clean()
    lote_nuevo.save()
    registrar_movimiento(
        lote_nuevo,
        MovimientoInventario.Tipo.ENTRADA,
        cantidad,
        motivo=f"Corrección: reemplaza a lote {lote_incorrecto.folio} ({lote_incorrecto.producto.nombre})",
    )
    # registrar_movimiento() opera sobre su propia copia fresca del lote
    # (select_for_update), así que el objeto local se refresca antes de
    # devolverlo para que cantidad_disponible sea la real, no la de antes.
    lote_nuevo.refresh_from_db()

    detalles_orden = list(orden.detalles.all())
    if all(d.cantidad_recibida >= d.cantidad for d in detalles_orden):
        orden.estatus = orden.Estatus.RECIBIDA
    elif any(d.cantidad_recibida > 0 for d in detalles_orden):
        orden.estatus = orden.Estatus.PARCIAL
    orden.save(update_fields=["estatus", "updated_at", "updated_by"])

    return lote_nuevo
