from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.gastos.forms import VehiculoForm
from apps.gastos.models import Vehiculo


class VehiculoListView(PermissionRequiredMixin, ListView):
    permission_required = "gastos.view_vehiculo"
    model = Vehiculo
    template_name = "gastos/vehiculo_list.html"
    context_object_name = "vehiculos"
    extra_context = {"active_module": "expenses"}

    def get_queryset(self):
        return super().get_queryset().select_related("centro_costo")


class VehiculoCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "gastos.add_vehiculo"
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "gastos/vehiculo_form.html"
    success_url = reverse_lazy("gastos:vehiculo-list")
    success_message = "Unidad registrada correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la unidad. Revisa los campos.")
        return super().form_invalid(form)


class VehiculoUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "gastos.change_vehiculo"
    model = Vehiculo
    form_class = VehiculoForm
    template_name = "gastos/vehiculo_form.html"
    success_url = reverse_lazy("gastos:vehiculo-list")
    success_message = "Unidad actualizada correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la unidad. Revisa los campos.")
        return super().form_invalid(form)
