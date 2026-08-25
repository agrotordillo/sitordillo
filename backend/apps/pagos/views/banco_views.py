from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.pagos.forms import BancoForm
from apps.pagos.models import Banco


class BancoListView(ListView):
    model = Banco
    template_name = "pagos/banco_list.html"
    context_object_name = "bancos"
    extra_context = {"active_module": "purchases"}


class BancoCreateView(SuccessMessageMixin, CreateView):
    model = Banco
    form_class = BancoForm
    template_name = "pagos/banco_form.html"
    success_url = reverse_lazy("pagos:banco-list")
    success_message = "Banco creado correctamente."
    extra_context = {"active_module": "purchases"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el banco. Revisa los campos.")
        return super().form_invalid(form)


class BancoUpdateView(SuccessMessageMixin, UpdateView):
    model = Banco
    form_class = BancoForm
    template_name = "pagos/banco_form.html"
    success_url = reverse_lazy("pagos:banco-list")
    success_message = "Banco actualizado correctamente."
    extra_context = {"active_module": "purchases"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el banco. Revisa los campos.")
        return super().form_invalid(form)
