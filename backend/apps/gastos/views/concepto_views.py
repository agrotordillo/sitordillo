from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.gastos.forms import ConceptoGastoForm
from apps.gastos.models import ConceptoGasto


class ConceptoGastoListView(PermissionRequiredMixin, ListView):
    permission_required = "gastos.view_conceptogasto"
    model = ConceptoGasto
    template_name = "gastos/concepto_list.html"
    context_object_name = "conceptos"
    extra_context = {"active_module": "expenses"}

    def get_queryset(self):
        return super().get_queryset().select_related("grupo").order_by(
            "grupo__orden", "grupo__nombre", "-is_active", "nombre"
        )


class ConceptoGastoCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "gastos.add_conceptogasto"
    model = ConceptoGasto
    form_class = ConceptoGastoForm
    template_name = "gastos/concepto_form.html"
    success_url = reverse_lazy("gastos:concepto-list")
    success_message = "Concepto de gasto creado correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el concepto de gasto. Revisa los campos.")
        return super().form_invalid(form)


class ConceptoGastoUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "gastos.change_conceptogasto"
    model = ConceptoGasto
    form_class = ConceptoGastoForm
    template_name = "gastos/concepto_form.html"
    success_url = reverse_lazy("gastos:concepto-list")
    success_message = "Concepto de gasto actualizado correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el concepto de gasto. Revisa los campos.")
        return super().form_invalid(form)
