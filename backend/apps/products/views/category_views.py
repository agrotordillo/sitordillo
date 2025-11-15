# django imports
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib import messages
# local imports
from apps.products.models import Category
from apps.products.forms import CategoryForm


class CategoryCreateView(CreateView):
    """Vista para la creación de categorías de productos."""

    model = Category
    form_class = CategoryForm
    template_name = "apps/products/templates/category-form.html"
    success_url = reverse_lazy("products:category-list")

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
