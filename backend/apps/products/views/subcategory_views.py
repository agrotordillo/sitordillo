from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from django.contrib.auth.mixins import PermissionRequiredMixin
from apps.products.models import Subcategoria
from apps.products.forms import SubcategoryForm


class SubcategoryCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_subcategoria"
    model = Subcategoria
    form_class = SubcategoryForm
    template_name = "subcategories/subcategory_form.html"
    success_url = reverse_lazy("products:subcategory-list")
    success_message = "Subcategoría creada exitosamente."
    extra_context = {"active_module": "subcategories"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la subcategoría. Revisa los campos.")
        return super().form_invalid(form)


class SubcategoryUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "products.change_subcategoria"
    model = Subcategoria
    form_class = SubcategoryForm
    template_name = "subcategories/subcategory_form.html"
    success_url = reverse_lazy("products:subcategory-list")
    success_message = "Subcategoría actualizada correctamente."
    extra_context = {"active_module": "subcategories"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la subcategoría. Revisa los campos.")
        return super().form_invalid(form)


class SubcategoryListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_subcategoria"
    model = Subcategoria
    template_name = "subcategories/subcategory_list.html"
    context_object_name = "subcategories"
    extra_context = {"active_module": "subcategories"}

    def get_queryset(self):
        return super().get_queryset().select_related("categoria")
