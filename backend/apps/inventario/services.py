from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.products.models import Producto
from .models import (
    Conversion,
    EnsamblePaquete,
    Lote,
    MovimientoAlmacen,
    MovimientoAlmacenLote,
    MovimientoInventario,
    redondear_costo,
)

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


def bloquear_lotes(lote_ids):
    """Bloquea (SELECT ... FOR UPDATE) los lotes `lote_ids`, en orden de pk.
    Toda operación que mueve varios lotes los bloquea así, de una vez y en el
    mismo orden, antes de tocarlos: dos operaciones simultáneas sobre lotes
    en común se forman en fila en vez de bloquearse mutuamente (deadlock).
    Debe llamarse dentro de una transacción."""
    ids = sorted(set(lote_ids))
    if ids:
        list(Lote.objects.select_for_update().filter(pk__in=ids).order_by("pk").values_list("pk", flat=True))


def bloquear_existencias(almacen, productos):
    """Bloquea, en orden de pk, los lotes con existencia de `productos` en
    `almacen` antes de planear una salida FIFO/FEFO: así el plan se arma
    con las cantidades vigentes y ninguna otra salida puede tomar esos
    lotes a la mitad -sin esto, dos ventas simultáneas planeaban sobre el
    mismo lote y la segunda fallaba con "cantidad negativa" aunque hubiera
    existencia en otro lote (B18 en docs/AUDITORIA.md)-. Debe llamarse
    dentro de una transacción."""
    producto_ids = {getattr(producto, "pk", producto) for producto in productos}
    if not producto_ids:
        return
    list(
        Lote.objects.select_for_update()
        .filter(almacen=almacen, producto_id__in=producto_ids, cantidad_disponible__gt=0)
        .order_by("pk")
        .values_list("pk", flat=True)
    )


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
    bloquear_existencias(almacen, [producto])
    plan = seleccionar_lotes_para_salida(producto, almacen, cantidad, estrategia=estrategia)
    return [
        registrar_movimiento(lote, MovimientoInventario.Tipo.SALIDA, -tomar, motivo=motivo)
        for lote, tomar in plan
    ]


def _bloquear_linea_y_orden_de_compra(detalle_id):
    """Relee con la fila bloqueada la línea de compra y su orden: corregir o
    dar merma sobre la misma orden al mismo tiempo (o junto con una
    recepción) no debe pisar cantidad_recibida/cantidad_merma ni el total.

    Primero la orden y luego la línea, el mismo orden que la recepción
    (inventario.views.recepcion_views._recibir) y la edición de la orden
    (compras.views.orden_compra_views.OrdenCompraUpdateView): tomarlos al
    revés que ellas permitiría que dos operaciones se esperen mutuamente."""
    from apps.compras.models import OrdenCompra, OrdenCompraDetalle

    # La orden de una línea nunca cambia: se puede leer sin candado.
    orden_id = OrdenCompraDetalle.objects.filter(pk=detalle_id).values_list("orden_compra_id", flat=True).get()
    orden = OrdenCompra.objects.select_for_update().get(pk=orden_id)
    detalle = OrdenCompraDetalle.objects.select_for_update().get(pk=detalle_id)
    return detalle, orden


def _validar_cuenta_por_pagar_ajustable(orden):
    """Un ajuste que mueve el total de la orden no procede si su cuenta por
    pagar ya tiene pagos: invalidaría lo ya pagado."""
    from apps.pagos.models import CuentaPorPagar

    if CuentaPorPagar.objects.filter(orden_compra=orden, pagos__isnull=False).exists():
        raise ValueError(
            "Esta orden ya tiene pagos registrados en su cuenta por pagar; no se puede "
            "ajustar automáticamente. Resuélvelo manualmente."
        )


@transaction.atomic
def corregir_recepcion(lote_incorrecto, cantidad, producto_correcto, motivo=""):
    """Corrige una recepción donde se eligió el producto equivocado, para la
    parte del lote que todavía no se ha vendido ni movido: no revierte
    ventas, solo entradas de inventario.

    Anula `cantidad` del lote incorrecto (movimiento AJUSTE, nunca se edita
    cantidad_disponible directamente) y la traslada a un lote nuevo del
    producto correcto, en el mismo almacén, con el mismo costo/número de
    lote/caducidad (es la misma mercancía física, solo mal etiquetada).

    En la orden de compra se conserva la cantidad total ordenada: lo
    recibido pasa de una línea a la otra, y solo lo que excede lo que ya se
    había ordenado del producto correcto (o todo, si la orden no lo traía)
    se le quita a lo ordenado del producto equivocado -así un producto mal
    capturado en la orden deja de cobrarse y de esperarse, pero si ambos
    venían en la orden y solo se recibió en la fila equivocada, la línea
    equivocada sigue pendiente de recibir-. Si la línea equivocada se queda
    en 0 se elimina de la orden. Después se recalcula el estatus de la orden
    y, si ya tiene cuenta por pagar (sin pagos), su monto."""
    from apps.compras.models import OrdenCompraDetalle
    from apps.pagos.services import resincronizar_cuenta_por_pagar

    if lote_incorrecto.orden_compra_detalle_id is None:
        raise ValueError(
            "Este lote no está ligado a una línea de orden de compra; no se puede corregir aquí."
        )
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad a corregir debe ser mayor a cero.")
    if producto_correcto.pk == lote_incorrecto.producto_id:
        raise ValueError("Elige un producto distinto al que ya tiene el lote.")
    if producto_correcto.tipo == Producto.TipoProducto.PAQUETE:
        raise ValueError("Un paquete no se compra a un proveedor; elige el producto que realmente llegó.")

    detalle_incorrecto, orden = _bloquear_linea_y_orden_de_compra(lote_incorrecto.orden_compra_detalle_id)
    _validar_cuenta_por_pagar_ajustable(orden)

    lote_incorrecto = Lote.objects.select_for_update().get(pk=lote_incorrecto.pk)
    if cantidad > lote_incorrecto.cantidad_disponible:
        raise ValueError(
            f"No puedes corregir más de lo disponible en el lote ({lote_incorrecto.cantidad_disponible})."
        )
    corregible = detalle_incorrecto.cantidad_recibida - detalle_incorrecto.cantidad_merma
    if cantidad > corregible:
        raise ValueError(
            f"De esta línea solo quedan {corregible} recibidas sin merma; no se puede corregir más que eso."
        )

    motivo_final = motivo or f"Corrección: se recibió {producto_correcto.nombre} en su lugar"
    registrar_movimiento(lote_incorrecto, MovimientoInventario.Tipo.AJUSTE, -cantidad, motivo=motivo_final)

    detalle_correcto = (
        OrdenCompraDetalle.objects.select_for_update()
        .filter(orden_compra=orden, producto=producto_correcto)
        .first()
    )
    ordenado_antes = detalle_correcto.cantidad if detalle_correcto else Decimal("0.00")
    if detalle_correcto is None:
        detalle_correcto = OrdenCompraDetalle(
            orden_compra=orden,
            producto=producto_correcto,
            precio_unitario=detalle_incorrecto.precio_unitario,
            cantidad_recibida=Decimal("0.00"),
        )
    detalle_correcto.cantidad_recibida += cantidad
    detalle_correcto.cantidad = max(ordenado_antes, detalle_correcto.cantidad_recibida)
    excedente = detalle_correcto.cantidad - ordenado_antes
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

    # excedente <= cantidad y cantidad <= lo recibido sin merma, así que la
    # línea equivocada nunca queda con cantidad < cantidad_recibida; solo
    # llega a 0 cuando todo lo recibido de ella se corrigió.
    detalle_incorrecto.cantidad_recibida -= cantidad
    detalle_incorrecto.cantidad -= excedente
    if detalle_incorrecto.cantidad <= 0:
        # Sus lotes (ya en 0) conservan su historial en el kardex; solo
        # pierden el vínculo con esta línea (on_delete=SET_NULL).
        detalle_incorrecto.delete()
    else:
        detalle_incorrecto.full_clean()
        detalle_incorrecto.save(update_fields=["cantidad", "cantidad_recibida", "updated_at", "updated_by"])

    orden.actualizar_estatus_por_recepcion()
    resincronizar_cuenta_por_pagar(orden)
    return lote_nuevo


def impuestos_unitarios_de_linea(detalle, orden=None):
    """(iva, ieps) que causa UNA unidad de esta línea de compra, sin
    redondear: su precio menos el % de descuento de la orden, por las tasas
    del producto (el IEPS forma parte de la base del IVA, igual que en
    ProductoPrecio.importe_iva). Es lo que el proveedor deja de facturar por
    cada pieza dañada (ver registrar_merma_recepcion)."""
    orden = orden or detalle.orden_compra
    producto = detalle.producto
    base = (detalle.precio_unitario or Decimal("0")) * (Decimal("1") - orden.descuento_pct_total / Decimal("100"))
    tasa_ieps = (producto.tasa_ieps / Decimal("100")) if producto.aplica_ieps and producto.tasa_ieps else Decimal("0")
    tasa_iva = (producto.tasa_iva / Decimal("100")) if producto.tipo_iva == Producto.TipoIVA.GRAVADO else Decimal("0")
    ieps = base * tasa_ieps
    return (base + ieps) * tasa_iva, ieps


def sugerir_impuestos_de_merma(detalle, cantidad, orden=None):
    """(iva, ieps) a descontar de la orden por dar de baja `cantidad` de
    esta línea, redondeados a centavos y sin pasar de lo que la orden trae
    capturado (una orden sin IVA, por ejemplo con nota de remisión, no
    tiene nada que descontar)."""
    orden = orden or detalle.orden_compra
    iva_unitario, ieps_unitario = impuestos_unitarios_de_linea(detalle, orden)
    iva = (cantidad * iva_unitario).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    ieps = (cantidad * ieps_unitario).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return min(iva, orden.iva), min(ieps, orden.ieps)


@transaction.atomic
def registrar_merma_recepcion(lote, cantidad, motivo="", iva=None, ieps=None):
    """Da de baja `cantidad` de un lote ligado a una orden de compra por
    mercancía que llegó dañada. Es el caso típico de CEDIS: el proveedor
    entrega con nota de remisión, después se detecta que parte llegó en mal
    estado, y el proveedor acepta descontarlo y facturar solo por lo bueno.

    No toca cantidad_recibida (sigue reflejando lo que físicamente llegó,
    así que el estatus de la orden -recibida/parcial- no cambia); registra
    la merma en un campo aparte (cantidad_merma) que reduce lo que esa línea
    factura y paga (ver OrdenCompraDetalle.cantidad_facturable).

    El IVA y el IEPS de la orden son montos capturados de la factura, así
    que no bajan solos con el subtotal (B22 en docs/AUDITORIA.md): se
    descuentan `iva` e `ieps` -lo que trae la nota de crédito del
    proveedor-, o si no se indican, lo que sugiere
    sugerir_impuestos_de_merma. Las retenciones no se tocan: si cambian, se
    corrigen en la orden.

    Si la orden ya tiene una cuenta por pagar generada, se recalcula su
    monto_total para que quede en línea con la factura ajustada del
    proveedor; si esa cuenta ya tiene pagos aplicados, se rechaza para no
    invalidar pagos existentes."""
    from apps.pagos.services import resincronizar_cuenta_por_pagar

    if lote.orden_compra_detalle_id is None:
        raise ValueError(
            "Este lote no está ligado a una línea de orden de compra; no se puede reportar merma aquí."
        )
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad dañada debe ser mayor a cero.")

    detalle, orden = _bloquear_linea_y_orden_de_compra(lote.orden_compra_detalle_id)
    _validar_cuenta_por_pagar_ajustable(orden)

    lote = Lote.objects.select_for_update().get(pk=lote.pk)
    if cantidad > lote.cantidad_disponible:
        raise ValueError(f"No puedes dar de baja más de lo disponible en el lote ({lote.cantidad_disponible}).")
    sin_merma = detalle.cantidad_recibida - detalle.cantidad_merma
    if cantidad > sin_merma:
        raise ValueError(f"De esta línea solo quedan {sin_merma} recibidas sin merma.")

    iva_sugerido, ieps_sugerido = sugerir_impuestos_de_merma(detalle, cantidad, orden)
    iva = iva_sugerido if iva is None else iva
    ieps = ieps_sugerido if ieps is None else ieps
    for nombre, monto, de_la_orden in (("IVA", iva, orden.iva), ("IEPS", ieps, orden.ieps)):
        if monto < 0:
            raise ValueError(f"El {nombre} a descontar no puede ser negativo.")
        if monto > de_la_orden:
            raise ValueError(f"El {nombre} a descontar (${monto}) no puede ser mayor al de la orden (${de_la_orden}).")

    motivo_final = motivo or "Mercancía recibida en mal estado, descontada de la factura del proveedor"
    if iva or ieps:
        sufijo = f" (IVA -${iva}, IEPS -${ieps})"
        motivo_final = motivo_final[: 255 - len(sufijo)] + sufijo
    registrar_movimiento(lote, MovimientoInventario.Tipo.MERMA, -cantidad, motivo=motivo_final)

    detalle.cantidad_merma += cantidad
    detalle.full_clean()
    detalle.save(update_fields=["cantidad_merma", "updated_at", "updated_by"])

    if iva or ieps:
        orden.iva -= iva
        orden.ieps -= ieps
        orden.save(update_fields=["iva", "ieps", "updated_at", "updated_by"])

    resincronizar_cuenta_por_pagar(orden)


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
    esa salida si la conversión se rechaza.

    Si la receta tiene `limite_diario_origen`, se valida antes de tocar
    inventario: la suma de esta conversión más las que ya se hicieron ese
    mismo día con la misma receta en el mismo almacén no puede superarlo
    (ej. máximo 5 sacos/día, aunque lo normal sea convertir 2)."""
    if cantidad_origen is None or cantidad_origen <= 0:
        raise ValueError("La cantidad a convertir debe ser mayor a cero.")

    fecha = fecha or timezone.localdate()

    if receta.limite_diario_origen is not None:
        ya_convertido_hoy = Conversion.objects.filter(
            receta=receta, almacen=almacen, fecha=fecha
        ).aggregate(total=models.Sum("cantidad_origen_convertida"))["total"] or Decimal("0.00")
        disponible_hoy = receta.limite_diario_origen - ya_convertido_hoy
        if cantidad_origen > disponible_hoy:
            raise ValueError(
                f"Límite diario de esta receta superado: ya se convirtieron {ya_convertido_hoy} de "
                f"{receta.limite_diario_origen} permitidos hoy en este almacén; puedes convertir hasta "
                f"{max(disponible_hoy, Decimal('0.00'))} más."
            )

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

    # El lote destino guarda el costo a 2 decimales (ver redondear_costo):
    # el valor generado se calcula con ese mismo costo para que cuadre con
    # lo que de verdad queda valorizado en inventario.
    costo_destino = redondear_costo(producto_destino.precio_costo)
    valor_generado = (cantidad_destino * costo_destino).quantize(TWO_PLACES)

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
        fecha=fecha,
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
        costo_unitario=costo_destino,
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


@transaction.atomic
def registrar_ensamble_paquete(paquete, almacen, cantidad, fecha=None, observaciones=""):
    """Arma `cantidad` unidades de un producto tipo Paquete: descuenta cada
    componente de su receta (products.PaqueteComponente) por FIFO
    (registrar_salida, el mismo mecanismo que una venta), así que el valor
    consumido es el costo real de los componentes -no uno estimado-. El
    paquete armado entra en un lote nuevo a ese mismo costo real (B25 en
    docs/AUDITORIA.md): armar no sube ni baja el valor del inventario, y un
    paquete de promoción que vale igual o menos que sus partes se puede
    armar -su margen se ve al venderlo con la lista PROMOCION-. A diferencia
    de registrar_conversion, no se compara contra el costo de catálogo del
    paquete."""
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad a armar debe ser mayor a cero.")
    if paquete.tipo != Producto.TipoProducto.PAQUETE:
        raise ValueError(f"{paquete.nombre} no es un producto de tipo Paquete/Combo.")

    componentes = list(paquete.componentes.select_related("producto_componente"))
    if not componentes:
        raise ValueError(f"{paquete.nombre} no tiene componentes capturados; agrégalos antes de armarlo.")

    fecha = fecha or timezone.localdate()

    # Todos los componentes de una vez y en orden de pk (ver bloquear_lotes),
    # no uno por uno en el orden de la receta.
    bloquear_existencias(almacen, [c.producto_componente for c in componentes])
    valor_consumido = Decimal("0.00")
    for componente in componentes:
        cantidad_componente = (componente.cantidad * cantidad).quantize(TWO_PLACES)
        movimientos_salida = registrar_salida(
            componente.producto_componente,
            almacen,
            cantidad_componente,
            estrategia="fifo",
            motivo=f"Ensamble de paquete: {paquete.nombre}",
        )
        valor_consumido += sum(
            ((-movimiento.cantidad) * movimiento.lote.costo_unitario for movimiento in movimientos_salida),
            Decimal("0.00"),
        )
    valor_consumido = valor_consumido.quantize(TWO_PLACES)

    # El lote guarda el costo a 2 decimales (ver redondear_costo): el valor
    # generado se calcula con ese costo, así cuadra con lo que de verdad
    # queda valorizado (puede diferir de valor_consumido por centavos).
    costo_paquete = redondear_costo(valor_consumido / cantidad)
    valor_generado = (cantidad * costo_paquete).quantize(TWO_PLACES)

    ensamble = EnsamblePaquete(
        almacen=almacen,
        paquete=paquete,
        cantidad=cantidad,
        fecha=fecha,
        valor_consumido=valor_consumido,
        valor_generado=valor_generado,
        observaciones=observaciones,
    )
    ensamble.full_clean()
    ensamble.save()

    lote_destino = Lote(
        producto=paquete,
        almacen=almacen,
        numero_lote=f"Ensamble {ensamble.folio}",
        fecha_ingreso=ensamble.fecha,
        costo_unitario=costo_paquete,
        cantidad_inicial=cantidad,
        cantidad_disponible=Decimal("0.00"),
    )
    lote_destino.full_clean()
    lote_destino.save()
    registrar_movimiento(
        lote_destino,
        MovimientoInventario.Tipo.ENTRADA,
        cantidad,
        motivo=f"Ensamble {ensamble.folio}",
    )

    return ensamble


def ultimo_costo(producto):
    """Último costo de compra del producto: el del lote más reciente que
    entró por una orden de compra (ya trae el descuento del proveedor y el
    flete prorrateado, ver recepcion_compra_view). Si el producto nunca se
    ha comprado, su costo de catálogo."""
    costo = (
        Lote.objects.filter(producto=producto, orden_compra_detalle__isnull=False)
        .order_by("-fecha_ingreso", "-created_at")
        .values_list("costo_unitario", flat=True)
        .first()
    )
    if costo is not None:
        return costo
    return redondear_costo(producto.precio_costo)


def validar_stock_movimiento_almacen(almacen, lineas):
    """Igual que traspasos.services.validar_stock_disponible_traspaso: un
    mensaje por cada producto que no alcanza, sin mutar nada. `lineas` es
    un iterable de (producto, cantidad)."""
    errores = []
    for producto, cantidad in lineas:
        try:
            seleccionar_lotes_para_salida(producto, almacen, cantidad, estrategia="fifo")
        except ValueError as e:
            errores.append(f"{producto.nombre}: {e}")
    return errores


@transaction.atomic
def aplicar_movimiento_almacen(movimiento):
    """Afecta el inventario con un movimiento manual en borrador.

    Entradas: un lote nuevo por línea, valorizado al último costo de compra
    (ver ultimo_costo). Salidas: FIFO sobre el almacén; en la devolución en
    móvil, cada lote que sale del móvil genera su lote espejo en el almacén
    destino con el mismo costo, número de lote y caducidad (es la misma
    mercancía que regresa, igual que un traspaso).

    Se registra como AJUSTE -o MERMA- y no como ENTRADA/SALIDA para no
    mezclarse con compras y ventas en los reportes que las distinguen por
    tipo (p. ej. Existencia sin movimiento usa SALIDA como "última venta");
    el concepto real queda en el motivo de cada movimiento de inventario."""
    movimiento = MovimientoAlmacen.objects.select_for_update().get(pk=movimiento.pk)
    if movimiento.estado != MovimientoAlmacen.Estado.BORRADOR:
        raise ValueError("Solo se puede aplicar un movimiento en borrador.")
    movimiento.full_clean()

    detalles = list(movimiento.detalles.select_related("producto"))
    if not detalles:
        raise ValueError("El movimiento no tiene productos.")

    if not movimiento.es_entrada:
        bloquear_existencias(movimiento.almacen, [d.producto for d in detalles])
        errores = validar_stock_movimiento_almacen(
            movimiento.almacen, [(d.producto, d.cantidad) for d in detalles]
        )
        if errores:
            raise ValueError(" ".join(errores))

    tipo = (
        MovimientoInventario.Tipo.MERMA
        if movimiento.concepto == MovimientoAlmacen.Concepto.SALIDA_MERMA
        else MovimientoInventario.Tipo.AJUSTE
    )
    etiqueta = f"{movimiento.get_concepto_display()} {movimiento.folio}"

    for detalle in detalles:
        if movimiento.es_entrada:
            costo = ultimo_costo(detalle.producto)
            lote = Lote(
                producto=detalle.producto,
                almacen=movimiento.almacen,
                numero_lote=movimiento.folio,
                fecha_ingreso=movimiento.fecha,
                costo_unitario=costo,
                cantidad_inicial=detalle.cantidad,
                cantidad_disponible=Decimal("0.00"),
            )
            lote.full_clean()
            lote.save()
            registrar_movimiento(lote, tipo, detalle.cantidad, motivo=etiqueta)
            MovimientoAlmacenLote.objects.create(detalle=detalle, lote=lote, cantidad=detalle.cantidad)
        else:
            plan = seleccionar_lotes_para_salida(
                detalle.producto, movimiento.almacen, detalle.cantidad, estrategia="fifo"
            )
            valor = Decimal("0.00")
            for lote, cantidad in plan:
                registrar_movimiento(lote, tipo, -cantidad, motivo=etiqueta)
                lote_destino = None
                if movimiento.es_devolucion_movil:
                    lote_destino = Lote(
                        producto=lote.producto,
                        almacen=movimiento.almacen_destino,
                        numero_lote=lote.numero_lote,
                        fecha_ingreso=movimiento.fecha,
                        fecha_caducidad=lote.fecha_caducidad,
                        costo_unitario=lote.costo_unitario,
                        cantidad_inicial=cantidad,
                        cantidad_disponible=Decimal("0.00"),
                    )
                    lote_destino.full_clean()
                    lote_destino.save()
                    registrar_movimiento(
                        lote_destino, tipo, cantidad, motivo=f"{etiqueta} desde {movimiento.almacen.nombre}"
                    )
                MovimientoAlmacenLote.objects.create(
                    detalle=detalle, lote=lote, lote_destino=lote_destino, cantidad=cantidad
                )
                valor += cantidad * lote.costo_unitario
            costo = redondear_costo(valor / detalle.cantidad)

        detalle.costo_unitario = costo
        detalle.save(update_fields=["costo_unitario", "updated_at", "updated_by"])

    movimiento.estado = MovimientoAlmacen.Estado.APLICADO
    movimiento.fecha_aplicacion = timezone.now()
    movimiento.save(update_fields=["estado", "fecha_aplicacion", "updated_at", "updated_by"])
    return movimiento


@transaction.atomic
def cancelar_movimiento_almacen(movimiento, motivo=""):
    """Cancela un movimiento manual. En borrador solo cambia de estado (no
    había tocado existencias). Aplicado, registra el movimiento contrario
    -AJUSTE- sobre exactamente los mismos lotes que afectó (ver
    MovimientoAlmacenLote): las salidas regresan a su lote de origen y las
    entradas se descuentan del lote que crearon. Si de una entrada ya se
    vendió o movió parte, no alcanza para revertirla y se rechaza completa
    (@transaction.atomic deshace lo que ya se hubiera revertido)."""
    movimiento = MovimientoAlmacen.objects.select_for_update().get(pk=movimiento.pk)
    if movimiento.estado == MovimientoAlmacen.Estado.CANCELADO:
        raise ValueError("Este movimiento ya está cancelado.")

    if movimiento.estado == MovimientoAlmacen.Estado.APLICADO:
        etiqueta = f"Cancelación de {movimiento.folio}"
        afectados = list(
            MovimientoAlmacenLote.objects.filter(detalle__movimiento=movimiento).select_related(
                "lote__producto", "lote_destino"
            )
        )
        bloquear_lotes(
            [a.lote_id for a in afectados] + [a.lote_destino_id for a in afectados if a.lote_destino_id]
        )
        for afectado in afectados:
            try:
                if movimiento.es_entrada:
                    registrar_movimiento(afectado.lote, MovimientoInventario.Tipo.AJUSTE, -afectado.cantidad, etiqueta)
                else:
                    if afectado.lote_destino_id:
                        registrar_movimiento(
                            afectado.lote_destino, MovimientoInventario.Tipo.AJUSTE, -afectado.cantidad, etiqueta
                        )
                    registrar_movimiento(afectado.lote, MovimientoInventario.Tipo.AJUSTE, afectado.cantidad, etiqueta)
            except ValueError:
                raise ValueError(
                    f"No se puede cancelar: parte de {afectado.lote.producto.nombre} que movió este documento ya "
                    "se vendió o se movió a otro lado. Registra un movimiento contrario por lo que quede."
                )

    movimiento.estado = MovimientoAlmacen.Estado.CANCELADO
    movimiento.fecha_cancelacion = timezone.now()
    movimiento.motivo_cancelacion = motivo
    movimiento.save(update_fields=["estado", "fecha_cancelacion", "motivo_cancelacion", "updated_at", "updated_by"])
    return movimiento
