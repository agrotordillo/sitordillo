from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from apps.core.filtros_producto import aplicar_filtros_producto, contexto_filtros_producto, leer_filtros_producto
from apps.core.parametros import fecha, filtrar_por_id, id_valido
from apps.core.scoping import almacen_principal, almacenes_visibles
from apps.products.busqueda import buscar_productos
from apps.products.models import Almacen
from apps.ventas.analisis import (
    AGRUPACIONES_PRECIO,
    AGRUPACIONES_PRODUCTO,
    AGRUPAR_DETALLE,
    MOSTRAR_EXISTENCIA_O_MOVIMIENTO,
    OPCIONES_MOSTRAR,
    analisis_por_precio,
    analisis_por_producto,
)
from apps.ventas.models import VentaDetalle

TIPOS_VENTA = [("venta", "Solo ventas"), ("remision", "Solo remisiones")]
LINEAS_POR_PAGINA = 100


def _rango_de_fechas(request):
    """(desde, hasta) del GET; sin fechas, del primer día del mes a hoy. Si
    vienen al revés se intercambian en vez de no mostrar nada."""
    hoy = timezone.localdate()
    desde = fecha(request.GET.get("fecha_desde")) or hoy.replace(day=1)
    hasta = fecha(request.GET.get("fecha_hasta")) or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def _almacenes_del_usuario(user):
    almacenes = Almacen.objects.filter(is_active=True).order_by("nombre")
    visibles = almacenes_visibles(user)
    if visibles is not None:
        almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
    return almacenes


def _filtro_de_productos(request):
    """Los filtros de catálogo (marca, línea, categoría, subcategoría, clase)
    y la búsqueda por nombre/SKU, como función para aplicarlos a cualquier
    queryset que llegue a Producto por `prefijo`."""
    filtros = leer_filtros_producto(request)
    buscar = request.GET.get("q", "").strip()

    def filtrar(queryset, prefijo):
        queryset = aplicar_filtros_producto(queryset, filtros, prefix=prefijo)
        return buscar_productos(queryset, buscar, prefijo)

    return filtrar


class AnalisisVentasProductoView(PermissionRequiredMixin, TemplateView):
    """Movimiento de cada producto en una sucursal y un periodo: existencia
    inicial, entradas, salidas, ventas y existencia final (ver
    ventas.analisis.analisis_por_producto). Es por una sola sucursal, como
    el kardex y como en scvweb: cada una tiene su propia existencia."""

    permission_required = "ventas.view_analisis_ventas"
    template_name = "ventas/analisis_producto.html"
    extra_context = {"active_module": "sales"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        desde, hasta = _rango_de_fechas(request)

        almacenes = _almacenes_del_usuario(request.user)
        almacen = None
        if request.GET.get("almacen"):
            almacen = almacenes.filter(pk=id_valido(request.GET["almacen"])).first()
        else:
            principal = almacen_principal(request.user)
            almacen = almacenes.filter(pk=principal.pk).first() if principal else almacenes.first()

        mostrar = request.GET.get("mostrar", "")
        if mostrar not in dict(OPCIONES_MOSTRAR):
            mostrar = MOSTRAR_EXISTENCIA_O_MOVIMIENTO
        agrupar = request.GET.get("agrupar", "")
        if agrupar not in {valor for valor, _, _ in AGRUPACIONES_PRODUCTO}:
            agrupar = ""

        if almacen is not None:
            context["resultado"] = analisis_por_producto(
                almacen, desde, hasta, filtrar=_filtro_de_productos(request), mostrar=mostrar, agrupar=agrupar,
            )

        context.update(contexto_filtros_producto(request))
        context.update({
            "almacenes": almacenes,
            "almacen": almacen,
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "q": request.GET.get("q", "").strip(),
            "mostrar": mostrar,
            "opciones_mostrar": OPCIONES_MOSTRAR,
            "agrupar": agrupar,
            "agrupar_etiqueta": dict((v, e) for v, e, _ in AGRUPACIONES_PRODUCTO).get(agrupar, ""),
            "agrupaciones": [(valor, etiqueta) for valor, etiqueta, _ in AGRUPACIONES_PRODUCTO],
        })
        return context


class AnalisisVentasPrecioView(PermissionRequiredMixin, TemplateView):
    """Ventas de un periodo repartidas por la lista de precios con la que se
    vendió cada línea, con costo y utilidad (ver
    ventas.analisis.analisis_por_precio)."""

    permission_required = "ventas.view_analisis_ventas"
    template_name = "ventas/analisis_precio.html"
    extra_context = {"active_module": "sales"}

    def get_detalles(self, desde, hasta):
        request = self.request
        detalles = VentaDetalle.objects.filter(
            venta__fecha_venta__date__gte=desde, venta__fecha_venta__date__lte=hasta,
        )
        visibles = almacenes_visibles(request.user)
        if visibles is not None:
            detalles = detalles.filter(venta__almacen__in=visibles)
        detalles = filtrar_por_id(detalles, "venta__almacen_id", request.GET.get("almacen"))
        detalles = filtrar_por_id(detalles, "venta__cliente_id", request.GET.get("cliente"))
        detalles = filtrar_por_id(detalles, "producto_id", request.GET.get("producto"))
        tipo = request.GET.get("tipo", "")
        if tipo == "venta":
            detalles = detalles.filter(venta__es_remision=False)
        elif tipo == "remision":
            detalles = detalles.filter(venta__es_remision=True)
        return _filtro_de_productos(request)(detalles, "producto__")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        desde, hasta = _rango_de_fechas(request)

        agrupar = request.GET.get("agrupar", "")
        if agrupar not in dict(AGRUPACIONES_PRECIO):
            agrupar = "producto"

        resultado = analisis_por_precio(self.get_detalles(desde, hasta), agrupar)
        if agrupar == AGRUPAR_DETALLE:
            paginator = Paginator(resultado["filas"], LINEAS_POR_PAGINA)
            page_obj = paginator.get_page(request.GET.get("page") or 1)
            resultado["filas"] = page_obj.object_list
            context.update({"page_obj": page_obj, "paginator": paginator, "is_paginated": paginator.num_pages > 1})

        filtros = contexto_filtros_producto(request, request.user, incluir_almacen=True, solo_sucursales=True)
        context.update(filtros)
        context.update({
            "resultado": resultado,
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "q": request.GET.get("q", "").strip(),
            "cliente_id": str(id_valido(request.GET.get("cliente")) or ""),
            "producto_id": str(id_valido(request.GET.get("producto")) or ""),
            "tipo": request.GET.get("tipo", "") if request.GET.get("tipo") in dict(TIPOS_VENTA) else "",
            "tipos_venta": TIPOS_VENTA,
            "agrupar": agrupar,
            "agrupar_etiqueta": dict(AGRUPACIONES_PRECIO)[agrupar],
            "agrupaciones": AGRUPACIONES_PRECIO,
            "es_detalle": agrupar == AGRUPAR_DETALLE,
        })
        return context
