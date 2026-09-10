from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.comisiones.forms import ComisionLineaForm, ComisionProductoForm
from apps.comisiones.models import ComisionLinea, ComisionProducto


class ComisionLineaListView(PermissionRequiredMixin, ListView):
    permission_required = "comisiones.view_comisionlinea"
    model = ComisionLinea
    template_name = "comisiones/comision_linea_list.html"
    context_object_name = "comisiones"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("linea")


class ComisionLineaCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "comisiones.add_comisionlinea"
    model = ComisionLinea
    form_class = ComisionLineaForm
    template_name = "comisiones/comision_linea_form.html"
    success_url = reverse_lazy("comisiones:comision-linea-list")
    success_message = "Comisión por línea creada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)


class ComisionLineaUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "comisiones.change_comisionlinea"
    model = ComisionLinea
    form_class = ComisionLineaForm
    template_name = "comisiones/comision_linea_form.html"
    success_url = reverse_lazy("comisiones:comision-linea-list")
    success_message = "Comisión por línea actualizada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)


class ComisionProductoListView(PermissionRequiredMixin, ListView):
    permission_required = "comisiones.view_comisionproducto"
    model = ComisionProducto
    template_name = "comisiones/comision_producto_list.html"
    context_object_name = "comisiones"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("producto")


class ComisionProductoCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "comisiones.add_comisionproducto"
    model = ComisionProducto
    form_class = ComisionProductoForm
    template_name = "comisiones/comision_producto_form.html"
    success_url = reverse_lazy("comisiones:comision-producto-list")
    success_message = "Comisión por producto creada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)


class ComisionProductoUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "comisiones.change_comisionproducto"
    model = ComisionProducto
    form_class = ComisionProductoForm
    template_name = "comisiones/comision_producto_form.html"
    success_url = reverse_lazy("comisiones:comision-producto-list")
    success_message = "Comisión por producto actualizada correctamente."
    extra_context = {"active_module": "sales"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar. Revisa los campos.")
        return super().form_invalid(form)
