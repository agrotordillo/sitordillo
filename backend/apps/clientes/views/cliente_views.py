from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.clientes.models import Cliente
from apps.clientes.forms import ClienteForm


class ClienteCreateView(SuccessMessageMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:cliente-list")
    success_message = "Cliente creado correctamente."
    extra_context = {"active_module": "clients"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el cliente. Revisa los campos.")
        return super().form_invalid(form)


class ClienteUpdateView(SuccessMessageMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:cliente-list")
    success_message = "Cliente actualizado correctamente."
    extra_context = {"active_module": "clients"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el cliente. Revisa los campos.")
        return super().form_invalid(form)


class ClienteListView(ListView):
    model = Cliente
    template_name = "clientes/cliente_list.html"
    context_object_name = "clientes"
    extra_context = {"active_module": "clients"}
