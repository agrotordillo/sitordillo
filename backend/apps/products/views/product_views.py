from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, OuterRef, Q, Subquery
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Producto, ProductoPrecio
from apps.products.forms import ProductForm

# (nombre de la ListaPrecio, nombre del campo anotado) para las 5 listas
# generales que se muestran como columnas en el listado de productos.
LISTAS_PRECIO_TABLA = [
    ("PUBLICO", "precio_publico"),
    ("MEDIO MAYOREO", "precio_medio_mayoreo"),
    ("MAYOREO", "precio_mayoreo"),
    ("SUB DISTRIBUIDOR", "precio_sub_distribuidor"),
    ("PROMOCION", "precio_promocion"),
]


class ProductCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "products.add_producto"
    model = Producto
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:product-list")
    success_message = "Producto creado correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el producto. Revisa los campos.")
        return super().form_invalid(form)


class ProductUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "products.change_producto"
    model = Producto
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:product-list")
    success_message = "Producto actualizado correctamente."
    extra_context = {"active_module": "products"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el producto. Revisa los campos.")
        return super().form_invalid(form)


class ProductListView(PermissionRequiredMixin, ListView):
    permission_required = "products.view_producto"
    model = Producto
    template_name = "products/product_list.html"
    context_object_name = "products"
    extra_context = {"active_module": "products"}
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(folio__icontains=q) | Q(sku__icontains=q) | Q(nombre__icontains=q)
            )
        annotations = {
            campo: Subquery(
                ProductoPrecio.objects.filter(
                    producto_id=OuterRef("pk"), lista_precio__nombre=nombre, almacen__isnull=True,
                ).values("precio_con_impuesto")[:1],
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
            for nombre, campo in LISTAS_PRECIO_TABLA
        }
        return queryset.annotate(**annotations)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context
