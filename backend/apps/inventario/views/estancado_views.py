from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.db.models import Max, OuterRef, Q, Subquery, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote, MovimientoInventario
from apps.products.models import Almacen

# Movimientos que meten stock físico por reabastecimiento -compra directa
# o traspaso recibido de CEDIS/otra sucursal- cuentan como "entrada" para
# este análisis (confirmado con el usuario). El traspaso comparte el
# mismo tipo tanto para la salida del origen como la entrada del destino,
# así que se filtra cantidad > 0 para quedarse solo con el lado que
# recibe.
TIPOS_ENTRADA = [MovimientoInventario.Tipo.ENTRADA, MovimientoInventario.Tipo.TRASPASO]

PAGINATE_BY = 50


@permission_required("inventario.view_lote", raise_exception=True)
def existencia_sin_movimiento_view(request):
    """Productos con existencia (>0) que no se han vendido en un tiempo
    -para decidir qué estrategia aplicar sobre mercancía que se está
    estancando-. Junto a la fecha de última venta también se muestra la
    de última entrada: si un producto no se vende hace mucho pero tampoco
    ha entrado mercancía nueva hace mucho, es genuinamente estancado; si
    entró hace poco, es normal que aún no se haya vuelto a vender -no es
    lo mismo-.

    Solo aparecen productos con existencia > 0: si no hay existencia no
    hay nada que "se esté estancando", es simplemente que no hay qué
    vender (ver Surtimiento por sucursal, que es el caso contrario)."""
    ultima_venta_sq = (
        MovimientoInventario.objects.filter(
            lote__producto=OuterRef("producto"),
            lote__almacen=OuterRef("almacen"),
            tipo=MovimientoInventario.Tipo.SALIDA,
        )
        .order_by()
        .values("lote__producto")
        .annotate(ultima=Max("fecha_movimiento"))
        .values("ultima")
    )
    ultima_entrada_sq = (
        MovimientoInventario.objects.filter(
            lote__producto=OuterRef("producto"),
            lote__almacen=OuterRef("almacen"),
            tipo__in=TIPOS_ENTRADA,
            cantidad__gt=0,
        )
        .order_by()
        .values("lote__producto")
        .annotate(ultima=Max("fecha_movimiento"))
        .values("ultima")
    )

    qs = (
        Lote.objects.filter(is_active=True)
        .values("producto", "producto__nombre", "producto__sku", "almacen", "almacen__nombre")
        .annotate(existencia=Sum("cantidad_disponible"))
        .filter(existencia__gt=0)
        .annotate(ultima_venta=Subquery(ultima_venta_sq), ultima_entrada=Subquery(ultima_entrada_sq))
    )

    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        qs = qs.filter(almacen__in=visibles.values_list("pk", flat=True))

    almacen_id = request.GET.get("almacen", "").strip()
    if almacen_id:
        qs = qs.filter(almacen_id=almacen_id)

    buscar = request.GET.get("q", "").strip()
    if buscar:
        qs = qs.filter(Q(producto__nombre__icontains=buscar) | Q(producto__sku__icontains=buscar))

    dias_minimos_raw = request.GET.get("dias_minimos", "").strip()
    dias_minimos = int(dias_minimos_raw) if dias_minimos_raw.isdigit() else 60

    hoy = timezone.localdate()
    filas = []
    for fila in qs:
        ultima_venta = fila["ultima_venta"].date() if fila["ultima_venta"] else None
        ultima_entrada = fila["ultima_entrada"].date() if fila["ultima_entrada"] else None
        dias_sin_venta = (hoy - ultima_venta).days if ultima_venta else None
        dias_desde_entrada = (hoy - ultima_entrada).days if ultima_entrada else None

        # "Nunca vendido" (dias_sin_venta=None) siempre pasa el filtro: es
        # el caso más urgente de todos, no hay manera de que "no llegue"
        # al mínimo de días pedido.
        if dias_sin_venta is not None and dias_sin_venta < dias_minimos:
            continue

        filas.append({
            **fila,
            "ultima_venta": ultima_venta,
            "ultima_entrada": ultima_entrada,
            "dias_sin_venta": dias_sin_venta,
            "dias_desde_entrada": dias_desde_entrada,
        })

    # Nunca vendido primero (el caso más urgente), luego de más a menos
    # días sin venta.
    filas.sort(key=lambda f: (f["dias_sin_venta"] is None, f["dias_sin_venta"] or 0), reverse=True)

    paginator = Paginator(filas, PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    almacenes = Almacen.objects.filter(is_active=True)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

    return render(
        request,
        "inventario/existencia_sin_movimiento_list.html",
        {
            "filas": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": paginator.num_pages > 1,
            "q": request.GET.get("q", ""),
            "almacen_id": almacen_id,
            "dias_minimos": dias_minimos,
            "almacenes": almacenes,
            "active_module": "warehouses",
        },
    )
