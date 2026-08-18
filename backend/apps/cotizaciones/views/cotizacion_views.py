from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.forms import CotizacionForm, CotizacionDetalleFormSet


class CotizacionListView(ListView):
    model = Cotizacion
    template_name = "cotizaciones/cotizacion_list.html"
    context_object_name = "cotizaciones"
    extra_context = {"active_module": "quotes"}

    def get_queryset(self):
        return super().get_queryset().select_related("cliente", "almacen", "venta").prefetch_related("detalles")


class CotizacionCreateView(CreateView):
    model = Cotizacion
    form_class = CotizacionForm
    template_name = "cotizaciones/cotizacion_form.html"
    success_url = reverse_lazy("cotizaciones:cotizacion-list")
    success_message = "Cotización registrada correctamente."
    extra_context = {"active_module": "quotes"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = CotizacionDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = CotizacionDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = CotizacionDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la cotización.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar la cotización. Revisa los campos.")
        return super().form_invalid(form)
