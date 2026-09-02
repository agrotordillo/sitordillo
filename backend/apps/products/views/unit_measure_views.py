from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from django.contrib.auth.mixins import PermissionRequiredMixin
from apps.products.models import UnidadMedida
from apps.products.forms import UnitMeasureForm


class UnitMeasureCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_unidadmedida"
    model = UnidadMedida
    form_class = UnitMeasureForm
    template_name = "units/unit_measure_form.html"
    success_url = reverse_lazy("products:unit-list")
    success_message = "Unidad de medida creada correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la unidad de medida. Revisa los campos.")
        return super().form_invalid(form)


class UnitMeasureListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_unidadmedida"
    model = UnidadMedida
    template_name = "units/unit_measure_list.html"
    context_object_name = "unit_measures"
    extra_context = {"active_module": "products"}
