from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Producto
from apps.products.forms import ProductForm


class ProductCreateView(SuccessMessageMixin, CreateView):
    model = Producto
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:product-list")
    success_message = "Producto creado correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el producto. Revisa los campos.")
        return super().form_invalid(form)


class ProductListView(ListView):
    model = Producto
    template_name = "products/product_list.html"
    context_object_name = "products"
    extra_context = {"active_module": "products"}
