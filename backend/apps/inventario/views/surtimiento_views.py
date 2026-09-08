from decimal import Decimal

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.views.generic import ListView

from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote
from apps.products.models import Almacen, ProductoStockSucursal


class SurtimientoListView(PermissionRequiredMixin, ListView):
    """Análisis de surtimiento por sucursal: qué producto está por debajo
    de su mínimo capturado en ProductoStockSucursal, en qué sucursal, y
    cuánto haría falta para llegar a su máximo. Solo alerta sobre las
    combinaciones producto+sucursal que sí tienen un mínimo/máximo
    capturado -no todas, son miles de productos-. Es solo un reporte: no
    genera ningún Traspaso ni Orden de Compra automáticamente, eso queda
    a criterio de quien lo revise."""

    permission_required = "products.view_productostocksucursal"
    model = ProductoStockSucursal
    template_name = "inventario/surtimiento_list.html"
    context_object_name = "alertas"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 50

    def get_queryset(self):
        existencia_sq = (
            Lote.objects.filter(
                producto=OuterRef("producto_id"), almacen=OuterRef("almacen_id"), is_active=True,
            )
            .values("almacen")
            .annotate(total=Sum("cantidad_disponible"))
            .values("total")
        )

        qs = (
            ProductoStockSucursal.objects.select_related("producto", "almacen")
            .annotate(
                existencia_actual=Coalesce(
                    Subquery(existencia_sq, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    Decimal("0.00"),
                )
            )
            .annotate(faltante=F("stock_maximo") - F("existencia_actual"))
            .filter(existencia_actual__lt=F("stock_minimo"))
        )

        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            qs = qs.filter(almacen__in=visibles)

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(Q(producto__nombre__icontains=buscar) | Q(producto__sku__icontains=buscar))

        almacen_id = self.request.GET.get("almacen", "").strip()
        if almacen_id:
            qs = qs.filter(almacen_id=almacen_id)

        return qs.order_by("almacen__nombre", "producto__nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["almacen_id"] = self.request.GET.get("almacen", "")
        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes
        return context
