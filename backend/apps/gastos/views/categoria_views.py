from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.gastos.forms import CategoriaGastoForm
from apps.gastos.models import CategoriaGasto


class CategoriaGastoListView(ListView):
    model = CategoriaGasto
    template_name = "gastos/categoria_list.html"
    context_object_name = "categorias"
    extra_context = {"active_module": "expenses"}


class CategoriaGastoCreateView(SuccessMessageMixin, CreateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = "gastos/categoria_form.html"
    success_url = reverse_lazy("gastos:categoria-list")
    success_message = "Categoría creada correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la categoría. Revisa los campos.")
        return super().form_invalid(form)


class CategoriaGastoUpdateView(SuccessMessageMixin, UpdateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = "gastos/categoria_form.html"
    success_url = reverse_lazy("gastos:categoria-list")
    success_message = "Categoría actualizada correctamente."
    extra_context = {"active_module": "expenses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la categoría. Revisa los campos.")
        return super().form_invalid(form)
