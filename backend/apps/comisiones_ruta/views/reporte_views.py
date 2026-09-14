from decimal import Decimal

from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.comisiones_ruta.models import ComisionColaboradorLinea
from apps.core.scoping import almacen_principal, almacenes_visibles
from apps.products.models import Almacen
from apps.ventas.models import VentaDetalle

# Ventas en estas dos listas comisionan al % propio de cada colaborador+línea
# (ComisionColaboradorLinea); en cualquier otra lista (MAYOREO, SUB
# DISTRIBUIDOR, PROMOCION) el negocio siempre paga este % fijo, sin
# excepción -así lo confirmaron, una por una, las 14 hojas del Excel legado
# de comisiones (datos/COMISIONES P36.xlsx): la variación por colaborador y
# línea solo aparece en las columnas "Precio 1" (PUBLICO) y "Precio 2"
# (MEDIO MAYOREO); "Precio 3/4/5" siempre calculan *1%, para cualquiera.
LISTAS_PORCENTAJE_VARIABLE = {"PUBLICO", "MEDIO MAYOREO"}
PORCENTAJE_LISTAS_FIJAS = Decimal("1.00")


@permission_required("comisiones_ruta.view_comisioncolaboradorlinea", raise_exception=True)
def reporte_comisiones_ruta_view(request):
    """Comisión de vendedor de ruta por colaborador en un periodo: a
    diferencia de la comisión de mostrador (apps.comisiones, mismo % para
    cualquier empleado), aquí cada colaborador tiene su propio % por línea
    (ComisionColaboradorLinea). La atribución es la misma que en mostrador:
    quien LEVANTÓ EL PEDIDO -Cotizacion.created_by- o, si la venta se
    registró directa, quien la registró (Venta.created_by). Se calcula
    sobre toda venta del periodo -incluye a crédito- y se descuenta lo
    devuelto (DevolucionClienteDetalle), igual que en Kardex.

    Solo cuenta una línea si: (1) hay un colaborador identificado, (2) ese
    colaborador tiene un % capturado para la línea del producto, y (3) la
    línea de venta tiene una lista de precio registrada (VentaDetalle.
    lista_precio) -dato nuevo, así que las ventas anteriores a este cambio
    no la tienen y se excluyen; se cuentan aparte para que no se pierdan en
    silencio."""
    hoy = timezone.localdate()
    fecha_desde = parse_date(request.GET.get("fecha_desde", "")) or hoy.replace(day=1)
    fecha_hasta = parse_date(request.GET.get("fecha_hasta", "")) or hoy

    detalles = (
        VentaDetalle.objects.filter(
            venta__fecha_venta__date__gte=fecha_desde,
            venta__fecha_venta__date__lte=fecha_hasta,
        )
        .select_related(
            "producto", "producto__linea", "lista_precio",
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

    pct_tabla = {
        (colaborador_id, linea_id): porcentaje
        for colaborador_id, linea_id, porcentaje in ComisionColaboradorLinea.objects.values_list(
            "colaborador_id", "linea_id", "porcentaje"
        )
    }

    filas = []
    sin_lista_precio = 0
    for detalle in detalles:
        cotizacion = getattr(detalle.venta, "cotizacion_origen", None)
        empleado = cotizacion.created_by if cotizacion else detalle.venta.created_by
        if not empleado:
            continue

        linea_id = detalle.producto.linea_id
        pct_base = pct_tabla.get((empleado.pk, linea_id)) if linea_id else None
        if pct_base is None:
            continue

        if detalle.lista_precio_id is None:
            sin_lista_precio += 1
            continue
        pct = pct_base if detalle.lista_precio.nombre in LISTAS_PORCENTAJE_VARIABLE else PORCENTAJE_LISTAS_FIJAS

        cantidad_neta = detalle.cantidad - detalle.cantidad_devuelta
        if cantidad_neta <= 0:
            continue

        precio_neto_unitario = (detalle.subtotal / detalle.cantidad) if detalle.cantidad else Decimal("0.00")
        importe_neto = (precio_neto_unitario * cantidad_neta).quantize(Decimal("0.01"))
        comision = (importe_neto * pct / Decimal("100")).quantize(Decimal("0.01"))

        filas.append({
            "empleado": empleado,
            "venta": detalle.venta,
            "producto": detalle.producto,
            "lista_precio": detalle.lista_precio,
            "cantidad": cantidad_neta,
            "importe": importe_neto,
            "porcentaje": pct,
            "comision": comision,
        })

    colaboradores_en_periodo = {f["empleado"] for f in filas}

    empleado_id = request.GET.get("empleado", "").strip()
    if empleado_id:
        filas = [f for f in filas if str(f["empleado"].pk) == empleado_id]

    grupos_por_clave = {}
    for fila in filas:
        grupo = grupos_por_clave.setdefault(fila["empleado"].pk, {
            "empleado": fila["empleado"], "filas": [],
            "total_importe": Decimal("0.00"), "total_comision": Decimal("0.00"),
        })
        grupo["filas"].append(fila)
        grupo["total_importe"] += fila["importe"]
        grupo["total_comision"] += fila["comision"]

    grupos = sorted(
        grupos_por_clave.values(),
        key=lambda g: g["empleado"].get_full_name() or g["empleado"].username,
    )
    for grupo in grupos:
        grupo["plaza"] = almacen_principal(grupo["empleado"])

    almacenes = Almacen.objects.filter(is_active=True)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

    return render(
        request,
        "comisiones_ruta/reporte_comisiones_ruta.html",
        {
            "grupos": grupos,
            "total_general": sum((g["total_comision"] for g in grupos), Decimal("0.00")),
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "almacen_id": almacen_id,
            "empleado_id": empleado_id,
            "empleados": sorted(colaboradores_en_periodo, key=lambda u: u.get_full_name() or u.username),
            "almacenes": almacenes,
            "sin_lista_precio": sin_lista_precio,
            "active_module": "sales",
        },
    )
