# django imports
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy
# # local imports
from apps.products.models import Productos
from apps.products.forms import ProductForm

class ProductCreateView(CreateView):
    """Vista para la creación de productos."""
    
    model = Productos
    form_class = ProductForm
    template_name = "products/forms/product_form.html"
    success_url = reverse_lazy("products:product-create")
    success_message = "Producto creado correctamente."

class ProductListView(TemplateView):
    """Vista para la creación de productos."""
    
    template_name = "products/forms/product_list.html"