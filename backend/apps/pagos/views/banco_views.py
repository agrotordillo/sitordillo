from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.pagos.forms import BancoForm
from apps.pagos.models import Banco


class BancoListView(PermissionRequiredMixin, ListView):
    permission_required = "pagos.view_banco"
    model = Banco
    template_name = "pagos/banco_list.html"
    context_object_name = "bancos"
    extra_context = {"active_module": "purchases"}


class BancoCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "pagos.add_banco"
    model = Banco
    form_class = BancoForm
    template_name = "pagos/banco_form.html"
    success_url = reverse_lazy("pagos:banco-list")
    success_message = "Banco creado correctamente."
    extra_context = {"active_module": "purchases"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el banco. Revisa los campos.")
        return super().form_invalid(form)


class BancoUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "pagos.change_banco"
    model = Banco
    form_class = BancoForm
    template_name = "pagos/banco_form.html"
    success_url = reverse_lazy("pagos:banco-list")
    success_message = "Banco actualizado correctamente."
    extra_context = {"active_module": "purchases"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el banco. Revisa los campos.")
        return super().form_invalid(form)
