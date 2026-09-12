from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView, TemplateView

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen


class AnalisisCompraProductoListView(PermissionRequiredMixin, ListView):
    """Historial de compra por producto: a diferencia de Surtimiento por
    sucursal (que solo dice qué está por debajo del mínimo ahora), este
    reporte muestra cada línea de compra real -proveedor, número de
    factura, precio pagado, fecha- para poder analizar a quién y a qué
    precio se le ha comprado un producto a lo largo del tiempo."""

    permission_required = "compras.view_ordencompradetalle"
    model = OrdenCompraDetalle
    template_name = "compras/analisis_compra_producto_list.html"
    context_object_name = "detalles"
    extra_context = {"active_module": "purchases"}
    paginate_by = 50

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("producto", "orden_compra", "orden_compra__proveedor")
            .exclude(orden_compra__estatus="borrador")
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(
                Q(producto__nombre__icontains=buscar)
                | Q(producto__sku__icontains=buscar)
                | Q(orden_compra__proveedor__nombre_comercial__icontains=buscar)
                | Q(orden_compra__proveedor__nombre_fiscal__icontains=buscar)
                | Q(orden_compra__proveedor__rfc__icontains=buscar)
                | Q(orden_compra__documento__icontains=buscar)
            )

        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        if fecha_desde:
            qs = qs.filter(orden_compra__fecha_orden__gte=fecha_desde)
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
        if fecha_hasta:
            qs = qs.filter(orden_compra__fecha_orden__lte=fecha_hasta)

        return qs.order_by("-orden_compra__fecha_orden", "producto__nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["hay_filtros"] = bool(context["q"] or context["fecha_desde"] or context["fecha_hasta"])
        return context


MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


class AnalisisCompraAnualListView(PermissionRequiredMixin, TemplateView):
    """Tabla pivote producto × mes: cuánto se recibió de cada producto en
    cada mes del año seleccionado, más el total del año. Solo cuenta lo
    que realmente entró al almacén (cantidad_recibida), no lo ordenado
    pero aún no recibido, y solo de órdenes reales -se excluyen borrador
    (nunca se confirmó) y cancelada (no se concretó)."""

    permission_required = "compras.view_ordencompradetalle"
    template_name = "compras/analisis_compra_anual_list.html"
    extra_context = {"active_module": "purchases"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        anios_disponibles = list(
            OrdenCompra.objects.annotate(anio=ExtractYear("fecha_orden"))
            .order_by("-anio")
            .values_list("anio", flat=True)
            .distinct()
        )
        anio_actual = timezone.localdate().year
        anio = self.request.GET.get("anio", "").strip()
        anio = int(anio) if anio.isdigit() else (anios_disponibles[0] if anios_disponibles else anio_actual)

        producto_id = self.request.GET.get("producto", "").strip()
        proveedor_id = self.request.GET.get("proveedor", "").strip()
        almacen_id = self.request.GET.get("almacen", "").strip()

        detalles = (
            OrdenCompraDetalle.objects.filter(orden_compra__fecha_orden__year=anio)
            .exclude(orden_compra__estatus__in=[OrdenCompra.Estatus.BORRADOR, OrdenCompra.Estatus.CANCELADA])
        )
        if producto_id:
            detalles = detalles.filter(producto_id=producto_id)
        if proveedor_id:
            detalles = detalles.filter(orden_compra__proveedor_id=proveedor_id)
        if almacen_id:
            detalles = detalles.filter(orden_compra__almacen_destino_id=almacen_id)

        filas_planas = (
            detalles.annotate(mes=ExtractMonth("orden_compra__fecha_orden"))
            .values("producto_id", "producto__nombre", "producto__sku", "mes")
            .annotate(total_mes=Sum("cantidad_recibida"))
            .order_by("producto__nombre")
        )

        productos = {}
        for fila in filas_planas:
            producto = productos.setdefault(
                fila["producto_id"],
                {
                    "nombre": fila["producto__nombre"],
                    "sku": fila["producto__sku"],
                    "meses": [0] * 12,
                    "total": 0,
                },
            )
            producto["meses"][fila["mes"] - 1] = fila["total_mes"]
            producto["total"] += fila["total_mes"]

        filas = sorted(productos.values(), key=lambda p: p["nombre"])

        almacenes = Almacen.objects.filter(is_active=True)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))

        context["filas"] = filas
        context["meses"] = list(MESES_ABREV.values())
        context["anio"] = anio
        context["anios_disponibles"] = anios_disponibles
        context["producto_id"] = producto_id
        context["proveedor_id"] = proveedor_id
        context["almacen_id"] = almacen_id
        context["almacenes"] = almacenes
        context["hay_filtros"] = bool(producto_id or proveedor_id or almacen_id)
        return context
