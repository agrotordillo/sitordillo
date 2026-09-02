from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Sum
from django.views.generic import ListView

from apps.compras.models import OrdenCompra
from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote


class LoteListView(PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_lote"
    model = Lote
    template_name = "inventario/lote_list.html"
    context_object_name = "lotes"
    extra_context = {"active_module": "warehouses"}

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


class ExistenciaListView(PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_lote"
    template_name = "inventario/existencia_list.html"
    context_object_name = "existencias"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        queryset = Lote.objects.filter(is_active=True, cantidad_disponible__gt=0)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return (
            queryset.values("producto__nombre", "producto__sku", "almacen__nombre")
            .annotate(total=Sum("cantidad_disponible"))
            .order_by("producto__nombre", "almacen__nombre")
        )
