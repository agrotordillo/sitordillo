from django.db import models, transaction

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
