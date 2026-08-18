from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from apps.ventas.models import Venta
from apps.ventas.forms import VentaForm, VentaDetalleFormSet
from apps.ventas.services import procesar_lineas_venta, validar_stock_disponible


class VentaListView(ListView):
    model = Venta
    template_name = "ventas/venta_list.html"
    context_object_name = "ventas"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("cliente", "almacen").prefetch_related("detalles")


class VentaCreateView(CreateView):
    model = Venta
    form_class = VentaForm
    template_name = "ventas/venta_form.html"
    success_url = reverse_lazy("ventas:venta-list")
    success_message = "Venta registrada correctamente."
    extra_context = {"active_module": "sales"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = VentaDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = VentaDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = VentaDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        almacen = form.cleaned_data["almacen"]
        lineas = [
            (cd["producto"], cd["cantidad"], cd["estrategia_salida"])
            for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la venta.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        errores_stock = validar_stock_disponible(almacen, lineas)
        if errores_stock:
            for error in errores_stock:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            procesar_lineas_venta(self.object)

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar la venta. Revisa los campos.")
        return super().form_invalid(form)
