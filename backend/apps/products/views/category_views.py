from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Categoria
from apps.products.forms import CategoryForm


class CategoryCreateView(SuccessMessageMixin, CreateView):
    model = Categoria
    form_class = CategoryForm
    template_name = "categories/category_form.html"
    success_url = reverse_lazy("products:category-list")
    success_message = "Categoría creada exitosamente."
    extra_context = {"active_module": "categories"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la categoría. Revisa los campos.")
        return super().form_invalid(form)


class CategoryListView(ListView):
    model = Categoria
    template_name = "categories/category_list.html"
    context_object_name = "categories"
    extra_context = {"active_module": "categories"}
