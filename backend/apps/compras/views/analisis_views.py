from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.compras.models import OrdenCompraDetalle


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
