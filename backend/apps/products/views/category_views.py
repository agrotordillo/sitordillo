from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from django.contrib.auth.mixins import PermissionRequiredMixin
from apps.products.models import Categoria
from apps.products.forms import CategoryForm


class CategoryCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_categoria"
    model = Categoria
    form_class = CategoryForm
    template_name = "categories/category_form.html"
    success_url = reverse_lazy("products:category-list")
    success_message = "Categoría creada exitosamente."
    extra_context = {"active_module": "categories"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la categoría. Revisa los campos.")
        return super().form_invalid(form)


class CategoryUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "products.change_categoria"
    model = Categoria
    form_class = CategoryForm
    template_name = "categories/category_form.html"
    success_url = reverse_lazy("products:category-list")
    success_message = "Categoría actualizada correctamente."
    extra_context = {"active_module": "categories"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la categoría. Revisa los campos.")
        return super().form_invalid(form)


class CategoryListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_categoria"
    model = Categoria
    template_name = "categories/category_list.html"
    context_object_name = "categories"
    extra_context = {"active_module": "categories"}
