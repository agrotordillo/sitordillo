from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import Conversion, Lote, MovimientoInventario

TWO_PLACES = Decimal("0.01")


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


@transaction.atomic
def registrar_merma_recepcion(lote, cantidad, motivo=""):
    """Da de baja `cantidad` de un lote ligado a una orden de compra por
    mercancía que llegó dañada. Es el caso típico de CEDIS: el proveedor
    entrega con nota de remisión, después se detecta que parte llegó en mal
    estado, y el proveedor acepta descontarlo y facturar solo por lo bueno.

    No toca cantidad_recibida (sigue reflejando lo que físicamente llegó,
    así que el estatus de la orden -recibida/parcial- no cambia); registra
    la merma en un campo aparte (cantidad_merma) que reduce lo que esa línea
    factura y paga (ver OrdenCompraDetalle.cantidad_facturable). Si la orden
    ya tiene una cuenta por pagar generada, se recalcula su monto_total para
    que quede en línea con la factura ajustada del proveedor; si esa cuenta
    ya tiene pagos aplicados, se rechaza para no invalidar pagos existentes."""
    detalle = lote.orden_compra_detalle
    if detalle is None:
        raise ValueError(
            "Este lote no está ligado a una línea de orden de compra; no se puede reportar merma aquí."
        )
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad dañada debe ser mayor a cero.")
    if cantidad > lote.cantidad_disponible:
        raise ValueError("No puedes dar de baja más de lo disponible en el lote.")

    orden = detalle.orden_compra
    cuenta = getattr(orden, "cuenta_por_pagar", None)
    if cuenta is not None and cuenta.pagos.exists():
        raise ValueError(
            "Esta orden ya tiene pagos registrados en su cuenta por pagar; no se puede "
            "ajustar automáticamente. Resuélvelo manualmente."
        )

    motivo_final = motivo or "Mercancía recibida en mal estado, descontada de la factura del proveedor"
    registrar_movimiento(lote, MovimientoInventario.Tipo.MERMA, -cantidad, motivo=motivo_final)

    detalle.cantidad_merma = (detalle.cantidad_merma or Decimal("0.00")) + cantidad
    detalle.full_clean()
    detalle.save(update_fields=["cantidad_merma", "updated_at", "updated_by"])

    if cuenta is not None:
        cuenta.monto_total = orden.total
        cuenta.full_clean()
        cuenta.save(update_fields=["monto_total", "updated_at", "updated_by"])


@transaction.atomic
def registrar_conversion(receta, almacen, cantidad_origen, fecha=None, observaciones=""):
    """Transforma `cantidad_origen` del producto origen de una receta en el
    producto destino correspondiente, en un mismo almacén.

    El producto origen sale por FIFO (registrar_salida, el mismo mecanismo
    que una venta), así que el valor consumido es el costo real -no uno
    estimado-. El producto destino entra en un lote nuevo a su costo de
    catálogo (Producto.precio_costo). Se rechaza si el valor generado no
    supera al valor consumido: envasar siempre debe costar más que vender a
    granel (empaque, mano de obra), así que si no es así hay un costo de
    catálogo mal capturado en el producto destino -y como esto se valida
    después de descontar el producto origen, @transaction.atomic revierte
    esa salida si la conversión se rechaza."""
    if cantidad_origen is None or cantidad_origen <= 0:
        raise ValueError("La cantidad a convertir debe ser mayor a cero.")

    producto_origen = receta.producto_origen
    producto_destino = receta.producto_destino
    cantidad_destino = (cantidad_origen * receta.factor).quantize(TWO_PLACES)

    movimientos_salida = registrar_salida(
        producto_origen,
        almacen,
        cantidad_origen,
        estrategia="fifo",
        motivo=f"Conversión a {producto_destino.nombre}",
    )
    valor_consumido = sum(
        ((-movimiento.cantidad) * movimiento.lote.costo_unitario for movimiento in movimientos_salida),
        Decimal("0.00"),
    ).quantize(TWO_PLACES)

    valor_generado = (cantidad_destino * producto_destino.precio_costo).quantize(TWO_PLACES)

    if valor_generado <= valor_consumido:
        raise ValueError(
            f"El valor generado (${valor_generado}) no supera al valor consumido (${valor_consumido}): revisa el "
            f"costo de catálogo de {producto_destino.nombre}, envasar siempre debe costar más que vender a granel."
        )

    conversion = Conversion(
        almacen=almacen,
        receta=receta,
        cantidad_origen_convertida=cantidad_origen,
        cantidad_destino_generada=cantidad_destino,
        fecha=fecha or timezone.localdate(),
        valor_consumido=valor_consumido,
        valor_generado=valor_generado,
        observaciones=observaciones,
    )
    conversion.full_clean()
    conversion.save()

    lote_destino = Lote(
        producto=producto_destino,
        almacen=almacen,
        numero_lote=f"Conversión {conversion.folio}",
        fecha_ingreso=conversion.fecha,
        costo_unitario=producto_destino.precio_costo,
        cantidad_inicial=cantidad_destino,
        cantidad_disponible=Decimal("0.00"),
    )
    lote_destino.full_clean()
    lote_destino.save()
    registrar_movimiento(
        lote_destino,
        MovimientoInventario.Tipo.ENTRADA,
        cantidad_destino,
        motivo=f"Conversión {conversion.folio} desde {producto_origen.nombre}",
    )

    return conversion

    return detalle
