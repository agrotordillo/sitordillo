from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Marca
from apps.products.forms import BrandForm


class BrandCreateView(SuccessMessageMixin, CreateView):
    model = Marca
    form_class = BrandForm
    template_name = "brands/brand_form.html"
    success_url = reverse_lazy("products:brand-list")
    success_message = "Marca creada correctamente."
    extra_context = {"active_module": "brands"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la marca. Revisa los campos.")
        return super().form_invalid(form)


class BrandListView(ListView):
    model = Marca
    template_name = "brands/brand_list.html"
    context_object_name = "brands"
    extra_context = {"active_module": "brands"}
