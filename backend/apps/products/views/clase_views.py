from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Clase
from apps.products.forms import ClaseForm


class ClaseCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_clase"
    model = Clase
    form_class = ClaseForm
    template_name = "clases/clase_form.html"
    success_url = reverse_lazy("products:clase-list")
    success_message = "Clase creada correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la clase. Revisa los campos.")
        return super().form_invalid(form)


class ClaseListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_clase"
    model = Clase
    template_name = "clases/clase_list.html"
    context_object_name = "clases"
    extra_context = {"active_module": "products"}
