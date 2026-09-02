import calendar
from datetime import date

from django.utils import timezone
from django.views.generic import TemplateView

from apps.gastos.services import resumen_comparativo


class ReportePuntoEquilibrioView(TemplateView):
    """Comparativo mensual de ventas vs. gasto real (directo + distribuido)
    por sucursal. No es el punto de equilibrio contable completo -para eso
    falta separar el costo variable de la mercancía vendida-, pero da el
    control operativo inmediato de si cada sucursal vendió más de lo que
    gastó ese mes."""

    template_name = "gastos/reporte.html"
    extra_context = {"active_module": "expenses"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        mes_param = self.request.GET.get("mes")
        hoy = timezone.localdate()
        if mes_param:
            try:
                anio, mes = (int(p) for p in mes_param.split("-"))
                fecha_inicio = date(anio, mes, 1)
            except (ValueError, TypeError):
                fecha_inicio = hoy.replace(day=1)
        else:
            fecha_inicio = hoy.replace(day=1)

        ultimo_dia = calendar.monthrange(fecha_inicio.year, fecha_inicio.month)[1]
        fecha_fin = fecha_inicio.replace(day=ultimo_dia)

        context["mes_seleccionado"] = fecha_inicio.strftime("%Y-%m")
        context["fecha_inicio"] = fecha_inicio
        context["fecha_fin"] = fecha_fin
        context["resumen"] = resumen_comparativo(fecha_inicio, fecha_fin)
        return context
