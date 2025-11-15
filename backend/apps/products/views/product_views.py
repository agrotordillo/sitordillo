# django imports
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib import messages
# local imports
from apps.products.models import Product
from apps.products.forms import ProductForm


class ProductCreateView(CreateView):
    """Vista para la creación de categorías de productos."""

    model = Product
    form_class = ProductForm
    template_name = "apps/products/templates/product-form.html"
    success_url = reverse_lazy("products:product-list")

    def form_valid(self, form):
        """
        Agrega mensaje de confirmación tras guardar exitosamente.
        """
        messages.success(self.request, "Categoría registrada correctamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Controla errores de validación con mensajes visibles.
        """
        messages.error(self.request, "Revisa los campos marcados en rojo.")
        return super().form_invalid(form)
