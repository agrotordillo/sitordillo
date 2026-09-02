from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from apps.gastos.models import CentroCosto, Gasto, GastoDistribucion
from apps.ventas.models import VentaDetalle


def validar_distribucion(importe_total, montos):
    """Valida que el reparto manual de un gasto compartido cuadre EXACTO
    contra el importe total. No promedia ni ajusta nada por su cuenta: si no
    cuadra, regresa el error para que el usuario corrija las cantidades a
    mano (p. ej. porque una sucursal con más personal consume más agua que
    otra y no le toca una parte igual)."""
    errores = []
    montos = [m for m in montos if m is not None]
    if not montos:
        errores.append("Agrega al menos una sucursal para distribuir el gasto.")
        return errores

    suma = sum(montos, Decimal("0.00"))
    if suma != importe_total:
        diferencia = importe_total - suma
        if diferencia > 0:
            detalle = f"faltan ${diferencia} por asignar"
        else:
            detalle = f"sobran ${-diferencia} asignados de más"
        errores.append(
            f"La suma de las cantidades por sucursal (${suma}) debe ser exactamente igual al importe del "
            f"gasto (${importe_total}): {detalle}."
        )
    return errores


def gasto_directo_por_centro(centro_costo, fecha_inicio, fecha_fin):
    """Suma de gastos no compartidos registrados directamente contra este
    centro de costo en el periodo."""
    total = Gasto.objects.filter(
        centro_costo=centro_costo,
        es_compartido=False,
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    ).aggregate(total=Sum("importe"))["total"]
    return total or Decimal("0.00")


def gasto_distribuido_por_centro(centro_costo, fecha_inicio, fecha_fin):
    """Suma de lo que le corresponde a este centro de costo de gastos
    compartidos con otras sucursales, según el reparto manual capturado."""
    total = GastoDistribucion.objects.filter(
        centro_costo=centro_costo,
        gasto__es_compartido=True,
        gasto__fecha__gte=fecha_inicio,
        gasto__fecha__lte=fecha_fin,
    ).aggregate(total=Sum("monto"))["total"]
    return total or Decimal("0.00")


def ventas_por_almacen(almacen, fecha_inicio, fecha_fin):
    """Total vendido (neto de descuento) en el almacén/sucursal durante el
    periodo, agregado a nivel de línea de venta para no tener que recorrer
    cada `Venta` en Python."""
    neto = ExpressionWrapper(
        F("cantidad") * F("precio_unitario") * (Decimal("1") - F("descuento") / Decimal("100")),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    total = (
        VentaDetalle.objects.filter(
            venta__almacen=almacen,
            venta__fecha_venta__date__gte=fecha_inicio,
            venta__fecha_venta__date__lte=fecha_fin,
        )
        .annotate(neto=neto)
        .aggregate(total=Sum("neto"))["total"]
    )
    return total or Decimal("0.00")


def resumen_comparativo(fecha_inicio, fecha_fin, centros_costo_qs=None):
    """Comparativo de ventas vs. gasto total (directo + distribuido) por
    cada centro de costo de tipo Sucursal en el periodo dado. No promedia
    entre sucursales: cada una se calcula con su propio gasto real.

    `centros_costo_qs` permite acotar a un subconjunto (p. ej. las
    sucursales visibles para un usuario restringido); por default
    considera todas."""
    resumen = []
    centros = (centros_costo_qs if centros_costo_qs is not None else CentroCosto.objects.all()).filter(
        is_active=True, tipo=CentroCosto.Tipo.SUCURSAL
    ).select_related("almacen").order_by("nombre")
    for centro in centros:
        ventas = ventas_por_almacen(centro.almacen, fecha_inicio, fecha_fin) if centro.almacen_id else Decimal("0.00")
        gasto_directo = gasto_directo_por_centro(centro, fecha_inicio, fecha_fin)
        gasto_distribuido = gasto_distribuido_por_centro(centro, fecha_inicio, fecha_fin)
        gasto_total = gasto_directo + gasto_distribuido
        resumen.append({
            "centro_costo": centro,
            "ventas": ventas,
            "gasto_directo": gasto_directo,
            "gasto_distribuido": gasto_distribuido,
            "gasto_total": gasto_total,
            "resultado": ventas - gasto_total,
        })
    return resumen
