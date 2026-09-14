from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comisiones_ruta.forms import ComisionColaboradorLineaForm
from apps.comisiones_ruta.models import ComisionColaboradorLinea


class ComisionColaboradorLineaListView(PermissionRequiredMixin, ListView):
    permission_required = "comisiones_ruta.view_comisioncolaboradorlinea"
    model = ComisionColaboradorLinea
    template_name = "comisiones_ruta/comision_colaborador_linea_list.html"
    context_object_name = "comisiones"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("colaborador", "linea")


class ComisionColaboradorLineaCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "comisiones_ruta.add_comisioncolaboradorlinea"
    model = ComisionColaboradorLinea
    form_class = ComisionColaboradorLineaForm
    template_name = "comisiones_ruta/comision_colaborador_linea_form.html"
    success_url = reverse_lazy("comisiones_ruta:comision-colaborador-linea-list")
    success_message = "Comisión por colaborador creada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)


class ComisionColaboradorLineaUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "comisiones_ruta.change_comisioncolaboradorlinea"
    model = ComisionColaboradorLinea
    form_class = ComisionColaboradorLineaForm
    template_name = "comisiones_ruta/comision_colaborador_linea_form.html"
    success_url = reverse_lazy("comisiones_ruta:comision-colaborador-linea-list")
    success_message = "Comisión por colaborador actualizada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)
