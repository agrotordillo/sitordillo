from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from apps.gastos.forms import GastoDistribucionFormSet, GastoForm
from apps.gastos.models import Gasto
from apps.gastos.services import validar_distribucion


class GastoListView(ListView):
    model = Gasto
    template_name = "gastos/gasto_list.html"
    context_object_name = "gastos"
    extra_context = {"active_module": "expenses"}
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("centro_costo", "categoria", "proveedor")


class GastoCreateView(CreateView):
    model = Gasto
    form_class = GastoForm
    template_name = "gastos/gasto_form.html"
    success_url = reverse_lazy("gastos:gasto-list")
    success_message = "Gasto registrado correctamente."
    extra_context = {"active_module": "expenses"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = GastoDistribucionFormSet(self.request.POST, instance=self.object, prefix="distribuciones")
            else:
                data["formset"] = GastoDistribucionFormSet(instance=self.object, prefix="distribuciones")
        return data

    def form_valid(self, form):
        formset = GastoDistribucionFormSet(self.request.POST, instance=form.instance, prefix="distribuciones")
        es_compartido = form.cleaned_data.get("es_compartido")

        if es_compartido:
            if not formset.is_valid():
                return self.render_to_response(self.get_context_data(form=form, formset=formset))

            montos = [
                cd["monto"]
                for f in formset
                if (cd := f.cleaned_data) and cd.get("centro_costo") and not cd.get("DELETE")
            ]
            errores = validar_distribucion(form.cleaned_data["importe"], montos)
            if errores:
                for error in errores:
                    form.add_error(None, error)
                return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            if es_compartido:
                formset.instance = self.object
                formset.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar el gasto. Revisa los campos.")
        return super().form_invalid(form)
