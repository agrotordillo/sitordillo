from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.proveedores.models import Proveedor
from apps.proveedores.forms import ProveedorForm


class SupplierCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "proveedores.add_proveedor"
    model = Proveedor
    form_class = ProveedorForm
    template_name = "proveedores/proveedor_form.html"
    success_url = reverse_lazy("proveedores:supplier-list")
    success_message = "Proveedor creado correctamente."
    extra_context = {"active_module": "suppliers"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el proveedor. Revisa los campos.")
        return super().form_invalid(form)


class SupplierUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "proveedores.change_proveedor"
    model = Proveedor
    form_class = ProveedorForm
    template_name = "proveedores/proveedor_form.html"
    success_url = reverse_lazy("proveedores:supplier-list")
    success_message = "Proveedor actualizado correctamente."
    extra_context = {"active_module": "suppliers"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el proveedor. Revisa los campos.")
        return super().form_invalid(form)


class SupplierListView(PermissionRequiredMixin, ListView):
    permission_required = "proveedores.view_proveedor"
    model = Proveedor
    template_name = "proveedores/proveedor_list.html"
    context_object_name = "suppliers"
    extra_context = {"active_module": "suppliers"}
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset().select_related("regimen_fiscal")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(folio__icontains=q)
                | Q(rfc__icontains=q)
                | Q(nombre_fiscal__icontains=q)
                | Q(nombre_comercial__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context
