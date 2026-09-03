from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.pagos.models import ReciboPago


class ReciboPagoListView(PermissionRequiredMixin, ListView):
    """Listado de eventos de pago (un recibo puede agrupar varias cuentas
    del mismo proveedor pagadas juntas), con su folio consecutivo y,
    expandible, los adeudos que cubrió cada uno -igual que la pantalla
    "Pagos a proveedores" del sistema anterior."""

    permission_required = "pagos.view_recibopago"
    model = ReciboPago
    template_name = "pagos/recibo_pago_list.html"
    context_object_name = "recibos"
    extra_context = {"active_module": "purchases"}
    paginate_by = 30

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("proveedor", "forma_pago", "banco")
            .prefetch_related("pagos__cuenta_por_pagar__orden_compra")
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            queryset = queryset.filter(
                Q(proveedor__nombre_comercial__icontains=buscar)
                | Q(proveedor__nombre_fiscal__icontains=buscar)
                | Q(proveedor__rfc__icontains=buscar)
            )

        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        if fecha_desde:
            queryset = queryset.filter(fecha_pago__gte=fecha_desde)
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
        if fecha_hasta:
            queryset = queryset.filter(fecha_pago__lte=fecha_hasta)

        if self.request.GET.get("solo_activos") == "1":
            # "Realmente ya pagado": ningún pago del recibo está Inactivo
            # (pendiente de nota de crédito). Se filtra en la consulta -no
            # después, en Python- para que la paginación no quede
            # descuadrada contra el total real de resultados.
            # annotate() con agregados (Count) le quita a la consulta el
            # ordering por default de Meta -Django ya no la considera
            # "ordered"-, así que hay que repetirlo explícito o la
            # paginación queda con un orden no determinista entre páginas.
            queryset = queryset.annotate(
                total_pagos=Count("pagos"),
                pagos_inactivos=Count("pagos", filter=Q(pagos__is_active=False)),
            ).filter(total_pagos__gt=0, pagos_inactivos=0).order_by("-numero")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["solo_activos"] = self.request.GET.get("solo_activos") == "1"
        return context
