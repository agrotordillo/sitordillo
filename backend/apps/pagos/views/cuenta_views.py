from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from apps.compras.models import OrdenCompra
from apps.pagos.forms import GenerarCuentaForm
from apps.pagos.models import CuentaPorPagar
from apps.pagos.services import generar_cuenta_por_pagar


class CuentaPorPagarListView(PermissionRequiredMixin, ListView):
    permission_required = "pagos.view_cuentaporpagar"
    model = CuentaPorPagar
    template_name = "pagos/cuenta_list.html"
    context_object_name = "cuentas"
    extra_context = {"active_module": "purchases"}

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("orden_compra", "orden_compra__proveedor")
            .prefetch_related("pagos")
        )

        buscar = self.request.GET.get("q", "").strip()
        if buscar:
            qs = qs.filter(
                Q(orden_compra__proveedor__nombre_comercial__icontains=buscar)
                | Q(orden_compra__proveedor__nombre_fiscal__icontains=buscar)
                | Q(orden_compra__proveedor__rfc__icontains=buscar)
            )

        fecha_desde, fecha_hasta = self._rango_fechas()
        if fecha_desde:
            qs = qs.filter(fecha_vencimiento__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_vencimiento__lte=fecha_hasta)

        return qs.order_by(
            "orden_compra__proveedor__nombre_comercial",
            "orden_compra__proveedor__nombre_fiscal",
            "orden_compra__proveedor_id",
            "fecha_vencimiento",
        )

    def _rango_fechas(self):
        """Traduce el filtro de periodo (mes/semana/rango) a un par de fechas
        para filtrar por fecha_vencimiento. Devuelve (None, None) si no hay
        ningún filtro de fecha activo."""
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
        context["hay_filtros"] = bool(
            context["q"] or context["periodo"]
        )
        cuentas = context["cuentas"]
        context["grupos"] = self._agrupar_por_proveedor(cuentas)
        context["totales_generales"] = self._sumar_totales(cuentas)
        return context

    @staticmethod
    def _sumar_totales(cuentas):
        """Acumula, para un conjunto de cuentas, el total facturado, los
        impuestos trasladados (IVA/IEPS) y retenidos, y el saldo aún
        pendiente de cobro — cada monto viene directo de la orden de compra
        asociada (ya calculado y guardado ahí), nunca recalculado aquí."""
        totales = {
            "monto_total": Decimal("0.00"),
            "iva": Decimal("0.00"),
            "ieps": Decimal("0.00"),
            "retenciones": Decimal("0.00"),
            "saldo_pendiente": Decimal("0.00"),
        }
        for cuenta in cuentas:
            orden = cuenta.orden_compra
            totales["monto_total"] += cuenta.monto_total
            totales["iva"] += orden.iva
            totales["ieps"] += orden.ieps
            totales["retenciones"] += orden.retencion_iva + orden.retencion_isr
            totales["saldo_pendiente"] += cuenta.saldo_pendiente
        return totales

    def _agrupar_por_proveedor(self, cuentas):
        """Agrupa las cuentas (ya vienen ordenadas por proveedor desde
        get_queryset) calculando el total acumulado de cada grupo. Se arma
        aquí en Python -en vez de con {% regroup %}- para poder adjuntarle
        los totales a cada grupo sin depender de un filtro de plantilla que
        busque en un diccionario por clave variable."""
        grupos = []
        actual = None
        for cuenta in cuentas:
            proveedor = cuenta.proveedor
            if actual is None or actual["proveedor"].pk != proveedor.pk:
                actual = {"proveedor": proveedor, "cuentas": []}
                grupos.append(actual)
            actual["cuentas"].append(cuenta)
        for grupo in grupos:
            grupo["totales"] = self._sumar_totales(grupo["cuentas"])
        return grupos


@permission_required("pagos.add_cuentaporpagar", raise_exception=True)
def generar_cuenta_view(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)

    if hasattr(orden, "cuenta_por_pagar"):
        messages.info(request, "Esta orden de compra ya tiene una cuenta por pagar generada.")
        return redirect("compras:orden-list")

    if orden.estatus not in (OrdenCompra.Estatus.PARCIAL, OrdenCompra.Estatus.RECIBIDA):
        messages.error(request, "Solo se puede generar una cuenta por pagar de una orden ya recibida.")
        return redirect("compras:orden-list")

    if request.method == "POST":
        form = GenerarCuentaForm(request.POST)
        if form.is_valid():
            try:
                generar_cuenta_por_pagar(
                    orden,
                    fecha_emision=form.cleaned_data["fecha_emision"],
                    observaciones=form.cleaned_data["observaciones"],
                )
                messages.success(request, "Cuenta por pagar generada correctamente.")
                return redirect("compras:orden-list")
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = GenerarCuentaForm(initial={"fecha_emision": timezone.localdate()})

    return render(
        request,
        "pagos/generar_cuenta_form.html",
        {"orden": orden, "form": form, "active_module": "purchases"},
    )
