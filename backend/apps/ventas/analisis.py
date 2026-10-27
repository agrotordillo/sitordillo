"""Análisis de ventas por producto y por precio (control_ven_analisis_ventas_productos
y grid_ven_analisis_ventas_por_precio en scvweb). Aquí solo se calcula; los
filtros los lee la vista (ver views/analisis_views.py)."""

from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.inventario.models import MovimientoInventario
from apps.products.models import ListaPrecio, Producto
from apps.ventas.models import VentaDetalle, VentaDetalleLote

CERO = Decimal("0.00")

# --- Análisis por producto ---------------------------------------------------

# (valor del parámetro "agrupar", etiqueta, campo de Producto).
AGRUPACIONES_PRODUCTO = [
    ("linea", "Línea", "linea"),
    ("categoria", "Categoría", "categoria"),
    ("marca", "Marca", "marca"),
    ("clase", "Clase", "clase"),
]

MOSTRAR_EXISTENCIA_O_MOVIMIENTO = "existencia_o_movimiento"
MOSTRAR_CON_MOVIMIENTO = "con_movimiento"
MOSTRAR_TODOS = "todos"
OPCIONES_MOSTRAR = [
    (MOSTRAR_EXISTENCIA_O_MOVIMIENTO, "Con existencia o movimiento"),
    (MOSTRAR_CON_MOVIMIENTO, "Solo con movimiento en el periodo"),
    (MOSTRAR_TODOS, "Todos"),
]

COLUMNAS_PRODUCTO = ("inicial", "entradas", "salidas", "ventas", "ventas_historicas", "final")


def _totales_en_cero(columnas):
    return {columna: CERO for columna in columnas}


def _sumar(totales, fila, columnas):
    for columna in columnas:
        totales[columna] += fila[columna]


def analisis_por_producto(almacen, fecha_desde, fecha_hasta, *, filtrar=None, mostrar=MOSTRAR_EXISTENCIA_O_MOVIMIENTO, agrupar=""):
    """Existencia inicial, entradas, salidas, ventas y existencia final de
    cada producto en `almacen` entre `fecha_desde` y `fecha_hasta`
    (ambas incluidas), como el análisis de scvweb pero con un rango de
    fechas libre en vez de un mes.

    Todo sale de los movimientos de inventario, así que la existencia final
    cuadra con el kardex:
    - inicial: el saldo de los movimientos anteriores a fecha_desde.
    - entradas: todo lo que sumó en el periodo -compras, traspasos
      recibidos, ajustes de entrada, conversiones, ensambles y devoluciones
      de cliente (decisión del usuario: cuentan como entrada, no restan de
      la venta)-.
    - ventas: lo que salió por una venta (VentaDetalleLote, que también
      registra los componentes de un paquete vendido), por fecha de venta.
    - salidas: todo lo demás que restó -traspasos enviados, ajustes de
      salida, mermas, consumo de conversiones y ensambles-.
    No cuentan los apartados de pedido (MovimientoInventario.Tipo.PEDIDO):
    la mercancía apartada sigue físicamente en la sucursal, y al entregarse
    se registra como venta. Por eso la existencia final es la física, que
    puede ser mayor que la "disponible" si hay pedidos abiertos.

    Las ventas importadas de scv_web (Venta.id_legado) no tienen lotes ni
    movimientos: suman a "ventas" directo de sus renglones, pero no se
    restan de la existencia -nunca salieron del inventario de sitordillo, y
    restarlas daría existencias negativas- (decisión del usuario,
    2026-10-27). `ventas_historicas` dice cuánto de "ventas" es de ellas.

    `filtrar(queryset, prefijo)` aplica los filtros de producto de la vista
    (marca, línea, búsqueda...) a un queryset que llega a Producto por
    `prefijo`."""
    filtrar = filtrar or (lambda queryset, prefijo: queryset)

    movimientos = filtrar(
        MovimientoInventario.objects.filter(lote__almacen=almacen, fecha_movimiento__date__lte=fecha_hasta)
        .exclude(tipo=MovimientoInventario.Tipo.PEDIDO),
        "lote__producto__",
    )
    en_periodo = Q(fecha_movimiento__date__gte=fecha_desde)
    saldos = {
        fila["lote__producto"]: fila
        for fila in movimientos.values("lote__producto").annotate(
            inicial=Coalesce(Sum("cantidad", filter=Q(fecha_movimiento__date__lt=fecha_desde)), CERO),
            entradas=Coalesce(Sum("cantidad", filter=en_periodo & Q(cantidad__gt=0)), CERO),
            restado=Coalesce(Sum("cantidad", filter=en_periodo & Q(cantidad__lt=0)), CERO),
        )
    }
    vendido = dict(
        filtrar(
            VentaDetalleLote.objects.filter(
                lote__almacen=almacen,
                detalle__venta__fecha_venta__date__gte=fecha_desde,
                detalle__venta__fecha_venta__date__lte=fecha_hasta,
            ),
            "lote__producto__",
        )
        .values("lote__producto")
        .annotate(total=Sum("cantidad"))
        .values_list("lote__producto", "total")
    )
    vendido_historico = dict(
        filtrar(
            VentaDetalle.objects.filter(
                venta__almacen=almacen,
                venta__id_legado__isnull=False,
                venta__fecha_venta__date__gte=fecha_desde,
                venta__fecha_venta__date__lte=fecha_hasta,
            ),
            "producto__",
        )
        .values("producto")
        .annotate(total=Sum("cantidad"))
        .values_list("producto", "total")
    )

    sin_movimiento = {"inicial": CERO, "entradas": CERO, "restado": CERO}
    productos = Producto.objects.filter(pk__in={*saldos, *vendido_historico}).select_related(
        "marca", "linea", "categoria", "clase", "unidad_medida"
    )
    filas = []
    for producto in productos:
        saldo = saldos.get(producto.pk, sin_movimiento)
        ventas = vendido.get(producto.pk, CERO)
        historicas = vendido_historico.get(producto.pk, CERO)
        fila = {
            "producto": producto,
            "inicial": saldo["inicial"],
            "entradas": saldo["entradas"],
            # Lo vendido también es un movimiento negativo: se separa aquí
            # para no contarlo dos veces.
            "salidas": -saldo["restado"] - ventas,
            "ventas": ventas + historicas,
            "ventas_historicas": historicas,
        }
        fila["final"] = fila["inicial"] + fila["entradas"] - fila["salidas"] - ventas
        movio = fila["entradas"] or fila["salidas"] or fila["ventas"]
        if mostrar == MOSTRAR_CON_MOVIMIENTO and not movio:
            continue
        if mostrar == MOSTRAR_EXISTENCIA_O_MOVIMIENTO and not (movio or fila["inicial"]):
            continue
        filas.append(fila)

    campo_grupo = dict((valor, campo) for valor, _, campo in AGRUPACIONES_PRODUCTO).get(agrupar)
    return _agrupar(filas, campo_grupo, COLUMNAS_PRODUCTO, orden=lambda fila: fila["producto"].nombre)


def _agrupar(filas, campo_grupo, columnas, *, orden):
    """Reparte `filas` en grupos por el catálogo `campo_grupo` del producto
    (o en uno solo, sin nombre, si no se agrupa), cada uno con sus
    subtotales, más el total general. Los productos sin ese catálogo van
    al final, en "Sin <catálogo>"."""
    grupos = {}
    for fila in sorted(filas, key=orden):
        catalogo = getattr(fila["producto"], campo_grupo) if campo_grupo else None
        clave = catalogo.pk if catalogo else None
        grupo = grupos.setdefault(clave, {
            "nombre": catalogo.nombre if catalogo else None,
            "filas": [],
            "totales": _totales_en_cero(columnas),
        })
        grupo["filas"].append(fila)
        _sumar(grupo["totales"], fila, columnas)

    totales = _totales_en_cero(columnas)
    for grupo in grupos.values():
        _sumar(totales, grupo["totales"], columnas)
    return {
        "grupos": sorted(grupos.values(), key=lambda g: (g["nombre"] is None, g["nombre"] or "")),
        "totales": totales,
        "productos": len(filas),
    }


# --- Análisis por precio -----------------------------------------------------

AGRUPAR_DETALLE = "detalle"
# (valor del parámetro "agrupar", etiqueta).
AGRUPACIONES_PRECIO = [
    ("producto", "Producto"),
    ("linea", "Línea"),
    ("categoria", "Categoría"),
    ("marca", "Marca"),
    ("cliente", "Cliente"),
    ("sucursal", "Sucursal"),
    (AGRUPAR_DETALLE, "Detalle (cada línea de venta)"),
]

COLUMNAS_PRECIO = ("cantidad", "importe", "total", "costo", "utilidad")

# Lo que la línea de venta no registró (ventas anteriores a que se guardara
# de qué lista salía el precio, ver VentaDetalle.lista_precio).
SIN_LISTA = "sin_lista"


def _clave_grupo(detalle, agrupar):
    """(clave, nombre, detalle secundario) del renglón al que va `detalle`."""
    producto = detalle.producto
    if agrupar == "producto":
        return producto.pk, producto.nombre, producto.sku
    if agrupar == "cliente":
        cliente = detalle.venta.cliente
        return cliente.pk, cliente.display_name, cliente.rfc
    if agrupar == "sucursal":
        return detalle.venta.almacen_id, detalle.venta.almacen.nombre, ""
    catalogo = getattr(producto, agrupar)
    if catalogo is None:
        return None, f"Sin {dict(AGRUPACIONES_PRECIO)[agrupar].lower()}", ""
    return catalogo.pk, catalogo.nombre, ""


def _costo_de_linea():
    """Lo que costó de verdad lo que salió en la línea (sus lotes, ya con los
    componentes si fue un paquete); para una venta sin ese registro, el costo
    histórico de la línea si es importada del sistema anterior
    (VentaDetalle.costo_unitario) y si no, el costo de catálogo, igual que al
    devolverla (ver ventas.services._reingresos_sin_registro_de_lotes)."""
    importe_lote = F("cantidad") * F("costo_unitario")
    del_lote = (
        VentaDetalleLote.objects.filter(detalle=OuterRef("pk"))
        .order_by()
        .values("detalle")
        .annotate(total=Sum(importe_lote, output_field=DecimalField(max_digits=16, decimal_places=4)))
        .values("total")
    )
    return Subquery(del_lote, output_field=DecimalField(max_digits=16, decimal_places=4))


def analisis_por_precio(detalles, agrupar="producto"):
    """Reparte el importe sin impuesto de las líneas `detalles` (un queryset
    de VentaDetalle ya filtrado por la vista) en una columna por lista de
    precios, como "Precio 1..5" en scvweb, más la venta con impuesto, el
    costo, la utilidad (importe sin impuesto - costo) y el margen.

    Los importes salen de las mismas propiedades que el ticket
    (VentaDetalle.subtotal e importe_sin_impuesto), línea por línea, para
    que cuadren al centavo con lo cobrado. Las devoluciones no se restan
    (decisión del usuario).

    `agrupar` es uno de AGRUPACIONES_PRECIO: un renglón por producto,
    catálogo, cliente o sucursal, o AGRUPAR_DETALLE para uno por línea."""
    detalles = (
        detalles.select_related(
            "producto__linea", "producto__categoria", "producto__marca", "producto__unidad_medida",
            "venta__cliente", "venta__almacen", "lista_precio",
        )
        .annotate(costo_lotes=_costo_de_linea())
        .order_by("venta__fecha_venta", "venta_id", "pk")
    )

    renglones = {}
    listas_usadas = set()
    for detalle in detalles.iterator(chunk_size=2000):
        importe = detalle.importe_sin_impuesto
        if detalle.costo_lotes is not None:
            costo = detalle.costo_lotes
        elif detalle.costo_unitario is not None:
            costo = detalle.cantidad * detalle.costo_unitario
        else:
            costo = detalle.cantidad * detalle.producto.precio_costo
        costo = costo.quantize(Decimal("0.01"))
        lista = detalle.lista_precio_id or SIN_LISTA
        listas_usadas.add(lista)

        if agrupar == AGRUPAR_DETALLE:
            clave, nombre, secundario = detalle.pk, detalle.producto.nombre, detalle.producto.sku
        else:
            clave, nombre, secundario = _clave_grupo(detalle, agrupar)
        renglon = renglones.setdefault(clave, {
            "nombre": nombre,
            "secundario": secundario,
            "por_lista": {},
            **_totales_en_cero(COLUMNAS_PRECIO),
        })
        if agrupar == AGRUPAR_DETALLE:
            renglon["detalle"] = detalle
        renglon["cantidad"] += detalle.cantidad
        renglon["importe"] += importe
        renglon["total"] += detalle.subtotal
        renglon["costo"] += costo
        renglon["utilidad"] += importe - costo
        renglon["por_lista"][lista] = renglon["por_lista"].get(lista, CERO) + importe

    listas = list(ListaPrecio.objects.filter(Q(is_active=True) | Q(pk__in=listas_usadas - {SIN_LISTA})))
    columnas_lista = [(lista.pk, lista.nombre) for lista in listas]
    if SIN_LISTA in listas_usadas:
        columnas_lista.append((SIN_LISTA, "Sin lista"))

    filas = list(renglones.values())
    if agrupar != AGRUPAR_DETALLE:
        filas.sort(key=lambda r: (-r["importe"], r["nombre"]))
    totales = _totales_en_cero(COLUMNAS_PRECIO)
    totales_lista = {clave: CERO for clave, _ in columnas_lista}
    for fila in filas:
        _sumar(totales, fila, COLUMNAS_PRECIO)
        fila["importes_lista"] = [fila["por_lista"].get(clave) for clave, _ in columnas_lista]
        fila["margen"] = _margen(fila)
        for clave, importe in fila["por_lista"].items():
            totales_lista[clave] += importe
    totales["margen"] = _margen(totales)
    totales["importes_lista"] = [totales_lista[clave] for clave, _ in columnas_lista]

    return {"filas": filas, "totales": totales, "columnas_lista": columnas_lista}


# --- Ventas por producto -------------------------------------------------------

# (valor del parámetro "agrupar", etiqueta, campo de VentaDetalle con la clave).
AGRUPACIONES_VENTAS = [
    ("producto", "Producto", "producto_id"),
    ("linea", "Línea", "producto__linea_id"),
    ("categoria", "Categoría", "producto__categoria_id"),
    ("marca", "Marca", "producto__marca_id"),
    ("clase", "Clase", "producto__clase_id"),
    ("sucursal", "Sucursal", "venta__almacen_id"),
    ("vendedor", "Vendedor", "vendedor_id"),
]
COLUMNAS_VENTAS = ("registros", "cantidad", "cantidad_auxiliar", "costo", "importe", "utilidad", "total")


def _nombres_de_grupo(agrupar, claves):
    """{clave: (nombre, detalle secundario)} de los renglones del reporte."""
    from apps.accounts.models import User
    from apps.products.models import Almacen, Categoria, Clase, Linea, Marca

    claves = [c for c in claves if c is not None]
    if agrupar == "producto":
        return {
            p.pk: (p.nombre, p.sku, p.unidad_medida_auxiliar.nombre if p.unidad_medida_auxiliar_id else "")
            for p in Producto.objects.filter(pk__in=claves).select_related("unidad_medida_auxiliar")
        }
    if agrupar == "vendedor":
        return {u.pk: (u.get_full_name() or u.username, u.username, "") for u in User.objects.filter(pk__in=claves)}
    modelo = {"linea": Linea, "categoria": Categoria, "marca": Marca, "clase": Clase, "sucursal": Almacen}[agrupar]
    return {pk: (nombre, "", "") for pk, nombre in modelo.objects.filter(pk__in=claves).values_list("pk", "nombre")}


def ventas_por_producto(detalles, agrupar="producto"):
    """Lo vendido en las líneas `detalles` (un queryset de VentaDetalle ya
    filtrado por la vista), un renglón por producto o por el catálogo de
    `agrupar` (ver AGRUPACIONES_VENTAS), como "Consulta - Ventas por
    producto" de scvweb (grid_ven_analisis_ventas): registros (líneas de
    venta), cantidad, cantidad auxiliar (cantidad x el contenido de la
    presentación, Producto.factor_unidad_auxiliar), costo, importe sin
    impuesto, utilidad e importe con impuesto. Las devoluciones no se restan,
    igual que en scvweb.

    Los importes salen de las mismas fórmulas que el ticket (ver
    ventas.models.subtotal_de_linea); el costo, como en analisis_por_precio:
    el de los lotes, si no el histórico de la línea importada y si no el de
    catálogo. Se leen valores sueltos en vez de objetos porque un mes de
    todas las sucursales son más de 100 mil líneas."""
    from apps.ventas.models import importe_sin_impuesto_de_linea, subtotal_de_linea, tasas_de_producto

    campo_clave = dict((valor, campo) for valor, _, campo in AGRUPACIONES_VENTAS)[agrupar]
    filas_bd = (
        detalles.annotate(
            costo_lotes=_costo_de_linea(),
            vendedor_id=Coalesce(
                "venta__cotizacion_origen__created_by", "venta__pedido_origen__created_by", "venta__created_by"
            ),
        )
        .order_by()
        .values_list(
            campo_clave, "cantidad", "precio_unitario", "descuento", "costo_lotes", "costo_unitario",
            "producto__precio_costo", "producto__factor_unidad_auxiliar",
            "producto__tipo_iva", "producto__tasa_iva", "producto__aplica_ieps", "producto__tasa_ieps",
        )
    )

    renglones = {}
    for (clave, cantidad, precio, descuento, costo_lotes, costo_unitario, precio_costo, factor,
         tipo_iva, tasa_iva, aplica_ieps, tasa_ieps) in filas_bd.iterator(chunk_size=5000):
        subtotal = subtotal_de_linea(cantidad, precio, descuento)
        importe = importe_sin_impuesto_de_linea(subtotal, *tasas_de_producto(tipo_iva, tasa_iva, aplica_ieps, tasa_ieps))
        if costo_lotes is not None:
            costo = costo_lotes
        else:
            costo = cantidad * (costo_unitario if costo_unitario is not None else precio_costo)
        costo = costo.quantize(Decimal("0.01"))

        renglon = renglones.setdefault(clave, _totales_en_cero(COLUMNAS_VENTAS))
        renglon["registros"] += 1
        renglon["cantidad"] += cantidad
        renglon["cantidad_auxiliar"] += cantidad * (factor or CERO)
        renglon["costo"] += costo
        renglon["importe"] += importe
        renglon["utilidad"] += importe - costo
        renglon["total"] += subtotal

    nombres = _nombres_de_grupo(agrupar, renglones)
    etiqueta = dict((valor, etiqueta) for valor, etiqueta, _ in AGRUPACIONES_VENTAS)[agrupar]
    filas = []
    for clave, renglon in renglones.items():
        nombre, secundario, unidad_auxiliar = nombres.get(clave, (f"Sin {etiqueta.lower()}", "", ""))
        renglon.update({"clave": clave, "nombre": nombre, "secundario": secundario, "unidad_auxiliar": unidad_auxiliar})
        renglon["margen"] = _margen(renglon)
        filas.append(renglon)
    filas.sort(key=lambda r: (r["clave"] is None, r["nombre"]))

    totales = _totales_en_cero(COLUMNAS_VENTAS)
    for fila in filas:
        _sumar(totales, fila, COLUMNAS_VENTAS)
    totales["margen"] = _margen(totales)
    return {"filas": filas, "totales": totales}


def _margen(fila):
    """Utilidad como % del importe sin impuesto, o None si no hubo importe."""
    if not fila["importe"]:
        return None
    return (fila["utilidad"] * 100 / fila["importe"]).quantize(Decimal("0.1"))
