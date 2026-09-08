from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.cobros.models import CuentaPorCobrar


class CuentaPorCobrarListView(PermissionRequiredMixin, ListView):
    """Espejo de pagos.views.cuenta_views.CuentaPorPagarListView, del lado
    del cliente. Sin desglose de IVA/IEPS en los totales -a diferencia de
    Cuentas por pagar- porque Venta no guarda esos montos por separado
    (ver ventas.models.Venta.total)."""

    permission_required = "cobros.view_cuentaporcobrar"
    model = CuentaPorCobrar
    template_name = "cobros/cuenta_list.html"
    context_object_name = "cuentas"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("venta", "venta__cliente")
            .prefetch_related("cobros")
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(
                Q(venta__cliente__nombre__icontains=buscar)
                | Q(venta__cliente__nombre_fiscal__icontains=buscar)
                | Q(venta__cliente__rfc__icontains=buscar)
            )

        fecha_desde, fecha_hasta = self._rango_fechas()
        if fecha_desde:
            qs = qs.filter(fecha_vencimiento__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_vencimiento__lte=fecha_hasta)

        return qs.order_by("venta__cliente__nombre", "venta__cliente_id", "fecha_vencimiento")

    def _rango_fechas(self):
        periodo = self.request.GET.get("periodo", "").strip()
        hoy = timezone.localdate()

        if periodo == "mes":
            desde = hoy.replace(day=1)
            siguiente_mes = (desde.replace(day=28) + timedelta(days=4)).replace(day=1)
            return desde, siguiente_mes - timedelta(days=1)

        if periodo == "semana":
            desde = hoy - timedelta(days=hoy.weekday())
            return desde, desde + timedelta(days=6)

        if periodo == "rango":
            desde = parse_date(self.request.GET.get("fecha_desde", ""))
            hasta = parse_date(self.request.GET.get("fecha_hasta", ""))
            return desde, hasta

        return None, None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        context["periodo"] = self.request.GET.get("periodo", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        context["hay_filtros"] = bool(context["q"] or context["periodo"])

        cuentas = context["cuentas"]
        context["grupos"] = self._agrupar_por_cliente(cuentas)
        context["totales_generales"] = self._sumar_totales(cuentas)
        return context

    @staticmethod
    def _sumar_totales(cuentas):
        totales = {"monto_total": Decimal("0.00"), "saldo_pendiente": Decimal("0.00")}
        for cuenta in cuentas:
            totales["monto_total"] += cuenta.monto_total
            totales["saldo_pendiente"] += cuenta.saldo_pendiente
        return totales

    def _agrupar_por_cliente(self, cuentas):
        grupos = []
        actual = None
        for cuenta in cuentas:
            cliente = cuenta.cliente
            if actual is None or actual["cliente"].pk != cliente.pk:
                actual = {"cliente": cliente, "cuentas": []}
                grupos.append(actual)
            actual["cuentas"].append(cuenta)
        for grupo in grupos:
            grupo["totales"] = self._sumar_totales(grupo["cuentas"])
        return grupos
