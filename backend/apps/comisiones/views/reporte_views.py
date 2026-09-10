from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import User
from apps.comisiones.models import ComisionLinea, ComisionProducto
from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen
from apps.ventas.models import VentaDetalle


@permission_required("comisiones.view_comisionlinea", raise_exception=True)
def reporte_comisiones_view(request):
    """Comisión de mostrador por empleado en un periodo: por cada línea de
    venta, se le atribuye a quien LEVANTÓ EL PEDIDO -el mostrador, vía
    Cotizacion.created_by- y, si la venta se registró directa (sin pasar
    por una cotización), a quien la registró (Venta.created_by, la misma
    persona en ese caso). Se calcula sobre toda venta del periodo, sin
    esperar a que se cobre -incluye ventas a crédito-, y se descuenta lo
    que se haya devuelto (DevolucionClienteDetalle), igual que en Kardex:
    la cancelación ya queda reflejada solo con considerarla, sin lógica
    aparte.

    Antes de este reporte, Venta/Cotizacion.created_by nunca se llenaba
    -ver apps.core.middleware.CurrentUserMiddleware, agregado junto con
    esto-, así que las ventas registradas antes de ese cambio no tienen
    a quién atribuírselas: aparecen agrupadas bajo "Sin atribuir" en vez
    de perderse en silencio.

    Solo cuentan los productos que tienen un % de comisión capturado
    (ComisionProducto, o si no, el de su línea vía ComisionLinea) -no se
    espera capturar esto para todo el catálogo, solo lo que de verdad da
    comisión."""
    hoy = timezone.localdate()
    fecha_desde = parse_date(request.GET.get("fecha_desde", "")) or hoy.replace(day=1)
    fecha_hasta = parse_date(request.GET.get("fecha_hasta", "")) or hoy

    detalles = (
        VentaDetalle.objects.filter(
            venta__fecha_venta__date__gte=fecha_desde,
            venta__fecha_venta__date__lte=fecha_hasta,
        )
        .select_related(
            "producto", "producto__linea",
            "venta", "venta__created_by", "venta__almacen",
            "venta__cotizacion_origen", "venta__cotizacion_origen__created_by",
        )
        .prefetch_related("devoluciones")
    )

    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        detalles = detalles.filter(venta__almacen__in=visibles)

    almacen_id = request.GET.get("almacen", "").strip()
    if almacen_id:
        detalles = detalles.filter(venta__almacen_id=almacen_id)

    pct_por_producto = dict(ComisionProducto.objects.values_list("producto_id", "porcentaje"))
    pct_por_linea = dict(ComisionLinea.objects.values_list("linea_id", "porcentaje"))

    filas = []
    for detalle in detalles:
        pct = pct_por_producto.get(detalle.producto_id)
        if pct is None and detalle.producto.linea_id:
            pct = pct_por_linea.get(detalle.producto.linea_id)
        if not pct:
            continue

        cantidad_neta = detalle.cantidad - detalle.cantidad_devuelta
        if cantidad_neta <= 0:
            continue

        cotizacion = getattr(detalle.venta, "cotizacion_origen", None)
        empleado = cotizacion.created_by if cotizacion else detalle.venta.created_by

        precio_neto_unitario = (detalle.subtotal / detalle.cantidad) if detalle.cantidad else Decimal("0.00")
        importe_neto = (precio_neto_unitario * cantidad_neta).quantize(Decimal("0.01"))
        comision = (importe_neto * pct / Decimal("100")).quantize(Decimal("0.01"))

        filas.append({
            "empleado": empleado,
            "venta": detalle.venta,
            "producto": detalle.producto,
            "cantidad": cantidad_neta,
            "importe": importe_neto,
            "porcentaje": pct,
            "comision": comision,
        })

    empleados_en_periodo = {f["empleado"] for f in filas if f["empleado"]}

    empleado_id = request.GET.get("empleado", "").strip()
    if empleado_id:
        filas = [f for f in filas if f["empleado"] and str(f["empleado"].pk) == empleado_id]

    grupos_por_clave = {}
    for fila in filas:
        clave = fila["empleado"].pk if fila["empleado"] else None
        grupo = grupos_por_clave.setdefault(clave, {
            "empleado": fila["empleado"], "filas": [],
            "total_importe": Decimal("0.00"), "total_comision": Decimal("0.00"),
        })
        grupo["filas"].append(fila)
        grupo["total_importe"] += fila["importe"]
        grupo["total_comision"] += fila["comision"]

    grupos = sorted(
        grupos_por_clave.values(),
        key=lambda g: (
            g["empleado"] is None,
            (g["empleado"].get_full_name() or g["empleado"].username) if g["empleado"] else "",
        ),
    )

    almacenes = Almacen.objects.filter(is_active=True)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

    return render(
        request,
        "comisiones/reporte_comisiones.html",
        {
            "grupos": grupos,
            "total_general": sum((g["total_comision"] for g in grupos), Decimal("0.00")),
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "almacen_id": almacen_id,
            "empleado_id": empleado_id,
            "empleados": sorted(empleados_en_periodo, key=lambda u: u.get_full_name() or u.username),
            "almacenes": almacenes,
            "active_module": "sales",
        },
    )
