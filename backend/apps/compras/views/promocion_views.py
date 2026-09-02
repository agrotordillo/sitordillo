from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.compras.models import PromocionProveedor
from apps.compras.forms import PromocionProveedorForm


class PromocionProveedorCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "compras.add_promocionproveedor"
    model = PromocionProveedor
    form_class = PromocionProveedorForm
    template_name = "compras/promocion_form.html"
    success_url = reverse_lazy("compras:promocion-list")
    success_message = "Promoción registrada correctamente."
    extra_context = {"active_module": "purchases"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la promoción. Revisa los campos.")
        return super().form_invalid(form)


class PromocionProveedorListView(PermissionRequiredMixin, ListView):
    permission_required = "compras.view_promocionproveedor"
    model = PromocionProveedor
    template_name = "compras/promocion_list.html"
    context_object_name = "promociones"
    extra_context = {"active_module": "purchases"}

    def get_queryset(self):
        return super().get_queryset().select_related("proveedor", "producto")
