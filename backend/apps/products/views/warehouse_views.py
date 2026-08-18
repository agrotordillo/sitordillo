from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Almacen
from apps.products.forms import WarehouseForm


class WarehouseCreateView(SuccessMessageMixin, CreateView):
    model = Almacen
    form_class = WarehouseForm
    template_name = "warehouses/warehouse_form.html"
    success_url = reverse_lazy("products:warehouse-list")
    success_message = "Almacén creado correctamente."
    extra_context = {"active_module": "warehouses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el almacén. Revisa los campos.")
        return super().form_invalid(form)


class WarehouseUpdateView(SuccessMessageMixin, UpdateView):
    model = Almacen
    form_class = WarehouseForm
    template_name = "warehouses/warehouse_form.html"
    success_url = reverse_lazy("products:warehouse-list")
    success_message = "Almacén actualizado correctamente."
    extra_context = {"active_module": "warehouses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el almacén. Revisa los campos.")
        return super().form_invalid(form)


class WarehouseListView(ListView):
    model = Almacen
    template_name = "warehouses/warehouse_list.html"
    context_object_name = "warehouses"
    extra_context = {"active_module": "warehouses"}
