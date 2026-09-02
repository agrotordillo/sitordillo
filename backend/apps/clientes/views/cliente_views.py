from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.clientes.models import Cliente
from apps.clientes.forms import ClienteForm


class ClienteCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "clientes.add_cliente"
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:cliente-list")
    success_message = "Cliente creado correctamente."
    extra_context = {"active_module": "clients"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el cliente. Revisa los campos.")
        return super().form_invalid(form)


class ClienteUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "clientes.change_cliente"
    model = Cliente
    form_class = ClienteForm
    template_name = "clientes/cliente_form.html"
    success_url = reverse_lazy("clientes:cliente-list")
    success_message = "Cliente actualizado correctamente."
    extra_context = {"active_module": "clients"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el cliente. Revisa los campos.")
        return super().form_invalid(form)


class ClienteListView(PermissionRequiredMixin, ListView):
    permission_required = "clientes.view_cliente"
    model = Cliente
    template_name = "clientes/cliente_list.html"
    context_object_name = "clientes"
    extra_context = {"active_module": "clients"}
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset().select_related("lista_precio")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(folio__icontains=q) | Q(rfc__icontains=q) | Q(nombre_fiscal__icontains=q) | Q(nombre__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context
