from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.views.generic import ListView

from apps.core.scoping import almacenes_visibles
from apps.inventario.models import Lote
from apps.products.models import Almacen, Producto


class CosteoProductoListView(PermissionRequiredMixin, ListView):
    """Compara, para cada producto que ya tiene compras registradas en el
    sistema (al menos un Lote), el costo capturado en su catálogo contra
    el costo real de sus lotes: el último costo pagado (lote más reciente,
    tenga o no existencia) y el costo promedio ponderado de lo que hay
    actualmente en existencia (solo lotes con cantidad_disponible > 0).
    Sirve para decidir si conviene manejar el costeo de un producto por
    "último costo" o por "promedio" (ver Producto.costeo), y para detectar
    productos cuyo costo de catálogo quedó desactualizado.

    No se creó ningún catálogo/tabla de historial de costo nuevo: los
    lotes ya capturan esa información (costo_unitario + cantidad + fecha
    de ingreso, ligados a la orden de compra de origen), así que este
    reporte solo la lee y la resume. Es de solo consulta: no modifica
    Producto.precio_costo ni nada más."""

    permission_required = "inventario.view_lote"
    model = Producto
    template_name = "inventario/costeo_producto_list.html"
    context_object_name = "productos"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 50

    def _almacen_ids_para_filtro(self):
        """None = sin restricción (se ve todo). Una lista = solo esos
        almacenes (por selección del filtro, o por las sucursales
        visibles del usuario si no hay selección explícita)."""
        almacen_id = self.request.GET.get("almacen", "").strip()
        if almacen_id:
            return [almacen_id]
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            return list(visibles.values_list("pk", flat=True))
        return None

    def get_queryset(self):
        almacen_ids = self._almacen_ids_para_filtro()
        lote_filter = {"is_active": True}
        if almacen_ids is not None:
            lote_filter["almacen_id__in"] = almacen_ids

        ultimo_sq = (
            Lote.objects.filter(producto=OuterRef("pk"), **lote_filter)
            .order_by("-fecha_ingreso", "-created_at")
            .values("costo_unitario")[:1]
        )
        promedio_sq = (
            Lote.objects.filter(producto=OuterRef("pk"), cantidad_disponible__gt=0, **lote_filter)
            .values("producto")
            .annotate(
                promedio=(
                    Sum(
                        F("costo_unitario") * F("cantidad_disponible"),
                        output_field=DecimalField(max_digits=18, decimal_places=6),
                    )
                    / Sum("cantidad_disponible", output_field=DecimalField(max_digits=14, decimal_places=4))
                )
            )
            .values("promedio")
        )

        # Solo entran productos con al menos un lote visible/seleccionado:
        # mostrar aquí los que nunca se han comprado en el sistema nuevo
        # solo llenaría el reporte de filas sin nada que comparar.
        existencia = Q(lotes__is_active=True)
        if almacen_ids is not None:
            existencia &= Q(lotes__almacen_id__in=almacen_ids)

        qs = (
            Producto.objects.filter(existencia)
            .distinct()
            .annotate(
                ultimo_costo=Subquery(ultimo_sq, output_field=DecimalField(max_digits=12, decimal_places=2)),
                costo_promedio=Subquery(promedio_sq, output_field=DecimalField(max_digits=14, decimal_places=4)),
            )
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(Q(nombre__icontains=buscar) | Q(sku__icontains=buscar) | Q(folio__icontains=buscar))

        return qs.order_by("nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        context["almacen_id"] = self.request.GET.get("almacen", "").strip()
        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes
        return context
