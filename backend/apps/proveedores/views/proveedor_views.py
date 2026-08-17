from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.proveedores.models import Proveedor
from apps.proveedores.forms import ProveedorForm


class SupplierCreateView(SuccessMessageMixin, CreateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = "proveedores/proveedor_form.html"
    success_url = reverse_lazy("proveedores:supplier-list")
    success_message = "Proveedor creado correctamente."
    extra_context = {"active_module": "suppliers"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el proveedor. Revisa los campos.")
        return super().form_invalid(form)


class SupplierListView(ListView):
    model = Proveedor
    template_name = "proveedores/proveedor_list.html"
    context_object_name = "suppliers"
    extra_context = {"active_module": "suppliers"}
