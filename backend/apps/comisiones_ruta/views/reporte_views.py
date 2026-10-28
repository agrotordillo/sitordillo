from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.db.models import Case, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.comisiones_ruta.models import ComisionColaboradorLinea
from apps.core.parametros import fecha, filtrar_por_id, id_valido
from apps.core.scoping import almacen_principal, almacenes_visibles
from apps.products.models import Almacen
from apps.ventas.models import DevolucionClienteDetalle, VentaDetalle

# Ventas en estas dos listas comisionan al `porcentaje` de la regla; en
# cualquier otra (MAYOREO, SUB DISTRIBUIDOR, PROMOCION), al
# `porcentaje_otras_listas` -1% para casi todos: así lo confirmaron, una por
# una, las hojas del Excel legado de comisiones (datos/COMISIONES P36.xlsx),
# donde "Precio 1" y "Precio 2" llevan el % de cada colaborador y "Precio
# 3/4/5" otro aparte-.
LISTAS_PORCENTAJE_VARIABLE = {"PUBLICO", "MEDIO MAYOREO"}
CERO = Decimal("0.00")


# Quien LEVANTÓ EL PEDIDO -Cotizacion/Pedido.created_by, ver
# Venta.documento_mostrador- o, si la venta se registró directa, quien la
# registró (Venta.created_by; en una venta importada de scv_web, su
# vendedor). Se resuelve en la consulta para no traer por cada línea la
# cotización, el pedido y sus usuarios.
VENDEDOR_ID = Case(
    When(venta__cotizacion_origen__isnull=False, then=F("venta__cotizacion_origen__created_by_id")),
    When(venta__pedido_origen__isnull=False, then=F("venta__pedido_origen__created_by_id")),
    default=F("venta__created_by_id"),
)
# Lo devuelto de la línea (DevolucionClienteDetalle), sumado en la consulta:
# es VentaDetalle.cantidad_devuelta sin un prefetch por cada línea.
DEVUELTO = Coalesce(
    Subquery(
        DevolucionClienteDetalle.objects.filter(venta_detalle=OuterRef("pk"))
        .values("venta_detalle")
        .annotate(total=Sum("cantidad"))
        .values("total")
    ),
    Value(Decimal("0.00")),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


def _reglas_que_aplican(detalle, fecha, propias, de_sucursal):
    """{colaborador_id: regla} para una línea de venta: por cada colaborador,
    la más específica de sus reglas que aplica (ver
    ComisionColaboradorLinea.especificidad). Una regla de "sus ventas en una
    sucursal" solo aplica a lo que vendió en esa sucursal, y lo cobrado con
    precio especial solo cuenta en las reglas que lo incluyen. Cada regla solo
    aplica en su vigencia y sus días de la semana (descansos y suplencias)."""
    almacen_id = detalle.venta.almacen_id
    candidatas = [*propias.get(detalle.vendedor_id, []), *de_sucursal.get(almacen_id, [])]
    elegidas = {}
    for regla in candidatas:
        if regla.alcance == regla.Alcance.PROPIAS_EN_SUCURSAL and regla.almacen_id != almacen_id:
            continue
        if not regla.aplica_en(fecha):
            continue
        if detalle.precio_especial and not regla.comisiona_precio_especial:
            continue
        if not regla.aplica_a(detalle.producto):
            continue
        actual = elegidas.get(regla.colaborador_id)
        if actual is None or regla.especificidad > actual.especificidad:
            elegidas[regla.colaborador_id] = regla
    return elegidas


def calcular_comisiones_ruta(request, con_detalle=False):
    """Comisión por colaborador en un periodo, según sus reglas
    (ComisionColaboradorLinea): sobre lo que vendió él -atribuido igual que
    en mostrador, ver _vendedor- o sobre toda la venta de una sucursal. Se
    calcula sobre toda venta del periodo -incluye a crédito-, sobre el
    importe sin impuestos (igual que el Excel con el que se paga hoy) y se
    descuenta lo devuelto (DevolucionClienteDetalle), igual que en Kardex.

    Una línea de venta sin lista de precio registrada (VentaDetalle.
    lista_precio: ventas a precio libre, o anteriores a que se guardara) no
    se puede repartir entre los dos % y se excluye; se cuenta aparte para que
    no se pierda en silencio.

    Con el historial de scv_web un mes son decenas de miles de líneas, así
    que el reporte se resume por regla; el detalle por venta solo se arma al
    filtrar un colaborador, o para todos con `con_detalle` (la descarga a
    Excel). Devuelve el contexto que usan la pantalla y la descarga."""
    hoy = timezone.localdate()
    fecha_desde = fecha(request.GET.get("fecha_desde")) or hoy.replace(day=1)
    fecha_hasta = fecha(request.GET.get("fecha_hasta")) or hoy
    almacen_id = request.GET.get("almacen", "").strip()
    empleado_id = request.GET.get("empleado", "").strip()
    empleado_pk = id_valido(empleado_id)

    reglas = list(ComisionColaboradorLinea.objects.select_related("colaborador", "linea", "categoria", "clase", "almacen"))
    propias, de_sucursal = defaultdict(list), defaultdict(list)
    for regla in reglas:
        if regla.alcance == regla.Alcance.SUCURSAL:
            de_sucursal[regla.almacen_id].append(regla)
        else:
            propias[regla.colaborador_id].append(regla)

    # Por rango de fecha y hora -no con __date- para que use el índice de
    # Venta.fecha_venta. Con el historial de scv_web son decenas de miles de
    # líneas al mes: solo se traen las columnas que se usan (cada modelo
    # cargado completo eran ~12 fechas por línea que convertir).
    zona = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(fecha_desde, time.min), zona)
    fin = timezone.make_aware(datetime.combine(fecha_hasta + timedelta(days=1), time.min), zona)
    detalles = (
        VentaDetalle.objects.filter(venta__fecha_venta__gte=inicio, venta__fecha_venta__lt=fin)
        .annotate(vendedor_id=VENDEDOR_ID, devuelto=DEVUELTO)
        .filter(Q(vendedor_id__in=list(propias)) | Q(venta__almacen_id__in=list(de_sucursal)))
        .select_related("producto", "lista_precio", "venta", "venta__almacen")
        .only(
            "cantidad", "precio_unitario", "descuento", "precio_especial", "lista_precio__nombre",
            "venta__folio", "venta__fecha_venta", "venta__almacen__nombre",
            "producto__nombre", "producto__sku", "producto__linea", "producto__categoria", "producto__clase",
            "producto__tipo_iva", "producto__tasa_iva", "producto__aplica_ieps", "producto__tasa_ieps",
        )
        .order_by("venta__fecha_venta", "pk")
    )
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        detalles = detalles.filter(venta__almacen__in=visibles)
    detalles = filtrar_por_id(detalles, "venta__almacen_id", almacen_id)

    # (colaborador_id, regla_id) -> totales de esa regla en el periodo.
    resumen = {}
    filas_por_colaborador = defaultdict(list)
    sin_lista_precio = 0
    for detalle in detalles.iterator(chunk_size=2000):
        elegidas = _reglas_que_aplican(detalle, detalle.venta.fecha_venta.astimezone(zona).date(), propias, de_sucursal)
        if not elegidas:
            continue
        if detalle.lista_precio_id is None:
            sin_lista_precio += 1
            continue
        cantidad_neta = detalle.cantidad - detalle.devuelto
        if cantidad_neta <= 0:
            continue
        precio_neto_unitario = (detalle.importe_sin_impuesto / detalle.cantidad) if detalle.cantidad else CERO
        importe_neto = (precio_neto_unitario * cantidad_neta).quantize(Decimal("0.01"))
        lista_variable = detalle.lista_precio.nombre in LISTAS_PORCENTAJE_VARIABLE

        for colaborador_id, regla in elegidas.items():
            pct = regla.porcentaje if lista_variable else regla.porcentaje_otras_listas
            if not pct:
                continue
            comision = (importe_neto * pct / Decimal("100")).quantize(Decimal("0.01"))
            totales = resumen.setdefault((colaborador_id, regla.pk), {
                "regla": regla, "vendido_variable": CERO, "vendido_otras": CERO, "comision": CERO,
            })
            totales["vendido_variable" if lista_variable else "vendido_otras"] += importe_neto
            totales["comision"] += comision
            if con_detalle or colaborador_id == empleado_pk:
                filas_por_colaborador[colaborador_id].append({
                    "venta": detalle.venta,
                    "regla": regla,
                    "vendedor": detalle.vendedor_id,
                    "producto": detalle.producto,
                    "lista_precio": detalle.lista_precio,
                    "cantidad": cantidad_neta,
                    "importe": importe_neto,
                    "porcentaje": pct,
                    "comision": comision,
                })

    # Los vendedores del detalle, de una vez (se guardó solo su id).
    vendedores = get_user_model().objects.in_bulk(
        {fila["vendedor"] for filas in filas_por_colaborador.values() for fila in filas} - {None}
    )
    for filas in filas_por_colaborador.values():
        for fila in filas:
            fila["vendedor"] = vendedores.get(fila["vendedor"])

    grupos_por_clave = {}
    for (colaborador_id, _), totales in resumen.items():
        grupo = grupos_por_clave.setdefault(colaborador_id, {
            "empleado": totales["regla"].colaborador, "reglas": [],
            "total_importe": CERO, "total_comision": CERO,
        })
        grupo["reglas"].append(totales)
        grupo["total_importe"] += totales["vendido_variable"] + totales["vendido_otras"]
        grupo["total_comision"] += totales["comision"]
    colaboradores_en_periodo = [g["empleado"] for g in grupos_por_clave.values()]

    if empleado_pk:
        grupos_por_clave = {k: g for k, g in grupos_por_clave.items() if k == empleado_pk}
    grupos = sorted(
        grupos_por_clave.values(),
        key=lambda g: g["empleado"].get_full_name() or g["empleado"].username,
    )
    for grupo in grupos:
        grupo["reglas"].sort(key=lambda t: t["regla"].descripcion)
        grupo["filas"] = filas_por_colaborador.get(grupo["empleado"].pk, [])
        grupo["plaza"] = almacen_principal(grupo["empleado"])

    almacenes = Almacen.objects.filter(is_active=True)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

    return {
        "grupos": grupos,
        "total_general": sum((g["total_comision"] for g in grupos), CERO),
        "fecha_desde": fecha_desde.isoformat(),
        "fecha_hasta": fecha_hasta.isoformat(),
        "periodo": (fecha_desde, fecha_hasta),
        "almacen_id": almacen_id,
        "almacen": almacenes.filter(pk=id_valido(almacen_id)).first() if almacen_id else None,
        "empleado_id": empleado_id,
        "empleados": sorted(colaboradores_en_periodo, key=lambda u: u.get_full_name() or u.username),
        "almacenes": almacenes,
        "sin_lista_precio": sin_lista_precio,
        "active_module": "sales",
    }


@permission_required("comisiones_ruta.view_comisioncolaboradorlinea", raise_exception=True)
def reporte_comisiones_ruta_view(request):
    return render(request, "comisiones_ruta/reporte_comisiones_ruta.html", calcular_comisiones_ruta(request))


@permission_required("comisiones_ruta.view_comisioncolaboradorlinea", raise_exception=True)
def reporte_comisiones_ruta_excel_view(request):
    """El mismo reporte, con los mismos filtros, en Excel: un resumen y una
    hoja por colaborador con sus reglas y el detalle por venta."""
    from apps.comisiones_ruta.excel import libro_comisiones_ruta

    contexto = calcular_comisiones_ruta(request, con_detalle=True)
    desde, hasta = contexto["periodo"]
    respuesta = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    respuesta["Content-Disposition"] = f'attachment; filename="comisiones_{desde:%Y%m%d}_{hasta:%Y%m%d}.xlsx"'
    libro_comisiones_ruta(contexto).save(respuesta)
    return respuesta
