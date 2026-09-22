from decimal import Decimal

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import ListView

from apps.fiscal.models import FormaPago
from apps.pagos.models import Banco, ReciboPago


@method_decorator(never_cache, name="dispatch")
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
            .prefetch_related("pagos__cuenta_por_pagar__orden_compra__detalles")
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            queryset = queryset.filter(
                Q(proveedor__nombre_comercial__icontains=buscar)
                | Q(proveedor__nombre_fiscal__icontains=buscar)
                | Q(proveedor__rfc__icontains=buscar)
            )

        documento = self.request.GET.get("documento", "").strip()
        if documento:
            queryset = queryset.filter(
                pagos__cuenta_por_pagar__orden_compra__documento__icontains=documento
            ).distinct()

        fecha_desde = parse_date(self.request.GET.get("fecha_desde", ""))
        if fecha_desde:
            queryset = queryset.filter(fecha_pago__gte=fecha_desde)
        fecha_hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
        if fecha_hasta:
            queryset = queryset.filter(fecha_pago__lte=fecha_hasta)

        forma_pago_ids = [v for v in self.request.GET.getlist("forma_pago") if v.strip()]
        if forma_pago_ids:
            queryset = queryset.filter(forma_pago_id__in=forma_pago_ids)

        banco_id = self.request.GET.get("banco", "").strip()
        if banco_id:
            queryset = queryset.filter(banco_id=banco_id)

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
            ).filter(total_pagos__gt=0, pagos_inactivos=0)

        if self.request.GET.get("orden") == "alfabetico":
            queryset = queryset.order_by("proveedor__nombre_comercial", "proveedor__nombre_fiscal")
        else:
            queryset = queryset.order_by("-numero")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["documento"] = self.request.GET.get("documento", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["solo_activos"] = self.request.GET.get("solo_activos") == "1"
        context["forma_pago_ids"] = [v for v in self.request.GET.getlist("forma_pago") if v.strip()]
        context["formas_pago"] = FormaPago.objects.all()
        context["banco_id"] = self.request.GET.get("banco", "")
        context["bancos"] = Banco.objects.all()
        context["orden"] = self.request.GET.get("orden", "")

        for recibo in context["recibos"]:
            self._anotar_totales_fiscales(recibo)

        return context

    @staticmethod
    def _anotar_totales_fiscales(recibo):
        """Subtotal/IVA/IEPS se calculan proporcionales a lo realmente
        pagado en cada `Pago` respecto al total de su cuenta por pagar -si
        una cuenta de $10,000 (con impuestos) se liquida en abonos de
        $3,000 y $2,000, cada recibo debe reflejar solo la fracción de
        impuestos que corresponde a lo que efectivamente pagó ese abono,
        no los impuestos completos de la orden de compra-."""
        subtotal_total = Decimal("0.00")
        iva_total = Decimal("0.00")
        ieps_total = Decimal("0.00")
        for pago in recibo.pagos.all():
            cuenta = pago.cuenta_por_pagar
            orden = cuenta.orden_compra
            if not cuenta.monto_total:
                continue
            proporcion = pago.monto_pagado / cuenta.monto_total
            subtotal_total += orden.subtotal * proporcion
            iva_total += orden.iva * proporcion
            ieps_total += orden.ieps * proporcion
        recibo.subtotal_total = subtotal_total
        recibo.iva_total = iva_total
        recibo.ieps_total = ieps_total
