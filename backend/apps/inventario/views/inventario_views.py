from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Sum
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.compras.models import OrdenCompra
from apps.core.filtros_producto import FiltrosProductoMixin
from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote


class LoteListView(FiltrosProductoMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_lote"
    model = Lote
    template_name = "inventario/lote_list.html"
    context_object_name = "lotes"
    extra_context = {"active_module": "warehouses"}
    filtro_producto_prefix = "producto__"
    filtro_incluir_almacen = True

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(cantidad_disponible__gt=0)
            .select_related("producto", "almacen", "orden_compra_detalle__orden_compra")
            .order_by("fecha_caducidad", "fecha_ingreso")
        )
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        orden_id = self.request.GET.get("orden")
        if orden_id:
            queryset = queryset.filter(orden_compra_detalle__orden_compra_id=orden_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orden_id = self.request.GET.get("orden")
        if orden_id:
            context["orden"] = OrdenCompra.objects.filter(pk=orden_id).first()
        return context


class ExistenciaListView(FiltrosProductoMixin, PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_lote"
    template_name = "inventario/existencia_list.html"
    context_object_name = "existencias"
    extra_context = {"active_module": "warehouses"}
    filtro_producto_prefix = "producto__"
    filtro_incluir_almacen = True

    def get_queryset(self):
        queryset = Lote.objects.filter(is_active=True, cantidad_disponible__gt=0)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)

        # Filtros de marca/línea/categoría/subcategoría/clase/sucursal deben
        # aplicarse ANTES del values()+annotate() de abajo: después de
        # agrupar, un .filter() ya actuaría como HAVING sobre lo agregado,
        # no como filtro de qué lotes entran al agrupamiento.
        queryset = self.aplicar_filtros_producto(queryset)

        # Fecha de ingreso del lote: cuándo entró esa mercancía, no cuándo
        # se registró en el sistema (created_at es solo auditoría).
        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        if fecha_desde:
            queryset = queryset.filter(fecha_ingreso__gte=fecha_desde)
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
        if fecha_hasta:
            queryset = queryset.filter(fecha_ingreso__lte=fecha_hasta)

        return (
            queryset.values("producto__nombre", "producto__sku", "almacen__nombre")
            .annotate(total=Sum("cantidad_disponible"))
            .order_by("producto__nombre", "almacen__nombre")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        return context
