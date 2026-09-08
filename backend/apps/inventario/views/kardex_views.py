from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils.dateparse import parse_date

from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote, MovimientoInventario
from apps.products.models import Almacen, Producto


@permission_required("inventario.view_movimientoinventario", raise_exception=True)
def kardex_producto_view(request):
    """Kardex de un producto en un almacén: la lista cronológica de TODOS
    sus movimientos de inventario (entradas, salidas, ajustes, mermas,
    traspasos, devoluciones -sin excluir ninguno-) con saldo corriendo.
    Como registrar_movimiento() nunca edita un movimiento ya guardado
    -toda corrección o cancelación se registra como un movimiento nuevo
    que descuenta o revierte al anterior (ver corregir_recepcion,
    registrar_merma_recepcion)-, este reporte ya refleja cualquier
    cancelación solo con listar todo en orden, sin lógica especial.

    Es por (producto, almacén) -no "todos los almacenes juntos"-, porque
    cada almacén tiene su propio saldo físico real; mezclarlos haría el
    saldo corriente ambiguo."""
    producto = None
    almacen = None
    filas = []
    saldo_inicial = Decimal("0.00")
    saldo_final = Decimal("0.00")
    existencia_actual = None

    producto_id = request.GET.get("producto", "").strip()
    almacen_id = request.GET.get("almacen", "").strip()
    fecha_desde = parse_date(request.GET.get("fecha_desde", ""))
    fecha_hasta = parse_date(request.GET.get("fecha_hasta", ""))

    almacenes = Almacen.objects.filter(is_active=True)
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

    if producto_id and almacen_id:
        producto = Producto.objects.filter(pk=producto_id).first()
        almacen = almacenes.filter(pk=almacen_id).first()

    if producto and almacen:
        base_qs = (
            MovimientoInventario.objects.filter(lote__producto=producto, lote__almacen=almacen)
            .select_related("lote")
            .order_by("fecha_movimiento", "created_at", "id")
        )

        if fecha_desde:
            anteriores = base_qs.filter(fecha_movimiento__date__lt=fecha_desde)
            saldo_inicial = anteriores.aggregate(total=Sum("cantidad"))["total"] or Decimal("0.00")
            base_qs = base_qs.filter(fecha_movimiento__date__gte=fecha_desde)
        if fecha_hasta:
            base_qs = base_qs.filter(fecha_movimiento__date__lte=fecha_hasta)

        saldo = saldo_inicial
        for movimiento in base_qs:
            saldo += movimiento.cantidad
            filas.append({
                "movimiento": movimiento,
                "entrada": movimiento.cantidad if movimiento.cantidad > 0 else None,
                "salida": -movimiento.cantidad if movimiento.cantidad < 0 else None,
                "saldo": saldo,
            })
        saldo_final = saldo

        existencia_actual = (
            Lote.objects.filter(producto=producto, almacen=almacen, is_active=True)
            .aggregate(total=Sum("cantidad_disponible"))["total"]
            or Decimal("0.00")
        )

    return render(
        request,
        "inventario/kardex_producto.html",
        {
            "producto": producto,
            "almacen": almacen,
            "almacenes": almacenes,
            "filas": filas,
            "saldo_inicial": saldo_inicial,
            "saldo_final": saldo_final,
            "existencia_actual": existencia_actual,
            "producto_id": producto_id,
            "almacen_id": almacen_id,
            "fecha_desde": request.GET.get("fecha_desde", ""),
            "fecha_hasta": request.GET.get("fecha_hasta", ""),
            "active_module": "warehouses",
        },
    )
