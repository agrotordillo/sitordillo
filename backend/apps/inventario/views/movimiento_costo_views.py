from decimal import Decimal

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Abs
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.core.scoping import almacenes_visibles
from apps.inventario.models import MovimientoInventario
from apps.products.models import Almacen

IMPORTE_EXPR = ExpressionWrapper(
    F("lote__costo_unitario") * Abs(F("cantidad")),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)
CANTIDAD_ABS_EXPR = ExpressionWrapper(Abs(F("cantidad")), output_field=DecimalField(max_digits=12, decimal_places=2))


class MovimientoCostoListView(PermissionRequiredMixin, ListView):
    """Movimientos de un almacén (todos los productos, no uno solo como en
    Kardex) valorizados a costo, en un listado plano SIN saldo corriente
    -a diferencia de Kardex, aquí no interesa la existencia que va
    quedando, sino el costo que representó cada entrada o salida, para
    poder sumarlas y analizarlas-. No se excluye ningún tipo de
    movimiento (incluye ajustes y mermas), así que cualquier corrección o
    cancelación ya aplicada queda reflejada en el listado sin lógica
    especial, igual que en Kardex."""

    permission_required = "inventario.view_movimientoinventario"
    model = MovimientoInventario
    template_name = "inventario/movimiento_costo_list.html"
    context_object_name = "movimientos"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 50

    def get_queryset(self):
        qs = (
            MovimientoInventario.objects.select_related("lote", "lote__producto", "lote__almacen")
            .annotate(importe=IMPORTE_EXPR, cantidad_abs=CANTIDAD_ABS_EXPR)
        )

        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            qs = qs.filter(lote__almacen__in=visibles)

        almacen_id = self.request.GET.get("almacen", "").strip()
        if almacen_id:
            qs = qs.filter(lote__almacen_id=almacen_id)

        producto_id = self.request.GET.get("producto", "").strip()
        if producto_id:
            qs = qs.filter(lote__producto_id=producto_id)

        tipo = self.request.GET.get("tipo", "").strip()
        if tipo:
            qs = qs.filter(tipo=tipo)

        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        if fecha_desde:
            qs = qs.filter(fecha_movimiento__date__gte=fecha_desde)
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
        if fecha_hasta:
            qs = qs.filter(fecha_movimiento__date__lte=fecha_hasta)

        return qs.order_by("-fecha_movimiento", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        totales = self.get_queryset().aggregate(
            total_entradas=Sum("importe", filter=Q(cantidad__gt=0)),
            total_salidas=Sum("importe", filter=Q(cantidad__lt=0)),
        )
        context["total_entradas"] = totales["total_entradas"] or Decimal("0.00")
        context["total_salidas"] = totales["total_salidas"] or Decimal("0.00")

        context["q_producto_id"] = self.request.GET.get("producto", "")
        context["almacen_id"] = self.request.GET.get("almacen", "")
        context["tipo"] = self.request.GET.get("tipo", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["tipos"] = MovimientoInventario.Tipo.choices

        almacenes = Almacen.objects.filter(is_active=True)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes
        return context
