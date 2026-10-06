from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import ListView

from apps.gastos.models import BitacoraAccesoGastos


class BitacoraAccesoListView(PermissionRequiredMixin, ListView):
    """Quién dio o quitó acceso a Gastos, a quién y cuándo. Como todo el
    módulo, ni el Administrador la ve sin la capacidad asignada."""

    permission_required = "gastos.view_bitacoraaccesogastos"
    model = BitacoraAccesoGastos
    template_name = "gastos/bitacora_acceso_list.html"
    context_object_name = "registros"
    extra_context = {"active_module": "expenses"}
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("usuario", "realizado_por")
