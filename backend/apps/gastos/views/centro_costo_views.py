from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.gastos.forms import CentroCostoForm
from apps.gastos.models import CentroCosto


class CentroCostoListView(ListView):
    model = CentroCosto
    template_name = "gastos/centro_costo_list.html"
    context_object_name = "centros_costo"
    extra_context = {"active_module": "expenses"}

    def get_queryset(self):
        return super().get_queryset().select_related("almacen")


class CentroCostoCreateView(SuccessMessageMixin, CreateView):
    model = CentroCosto
    form_class = CentroCostoForm
    template_name = "gastos/centro_costo_form.html"
    success_url = reverse_lazy("gastos:centro-costo-list")
    success_message = "Centro de costo creado correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el centro de costo. Revisa los campos.")
        return super().form_invalid(form)


class CentroCostoUpdateView(SuccessMessageMixin, UpdateView):
    model = CentroCosto
    form_class = CentroCostoForm
    template_name = "gastos/centro_costo_form.html"
    success_url = reverse_lazy("gastos:centro-costo-list")
    success_message = "Centro de costo actualizado correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el centro de costo. Revisa los campos.")
        return super().form_invalid(form)
