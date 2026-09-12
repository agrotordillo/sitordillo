from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Linea
from apps.products.forms import LineaForm


class LineaCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_linea"
    model = Linea
    form_class = LineaForm
    template_name = "lineas/linea_form.html"
    success_url = reverse_lazy("products:linea-list")
    success_message = "Línea creada correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la línea. Revisa los campos.")
        return super().form_invalid(form)


class LineaListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_linea"
    model = Linea
    template_name = "lineas/linea_list.html"
    context_object_name = "lineas"
    extra_context = {"active_module": "products"}
