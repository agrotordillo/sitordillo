from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, OuterRef, Q, Subquery
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.products.models import Categoria, Clase, Linea, Marca, Producto, ProductoPrecio
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


class NextUrlMixin:
    """Permite que "Guardar" y "Cancelar" regresen a la búsqueda/filtro
    desde donde se entró al formulario (?next=...) en vez de mandar
    siempre al listado sin filtros. El listado arma el enlace con
    ?next={{ request.get_full_path }} y el formulario reenvía ese mismo
    valor en un input oculto para que sobreviva a un reenvío por error
    de validación."""

    def get_next_url(self):
        return self.request.POST.get("next") or self.request.GET.get("next") or str(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_url"] = self.get_next_url()
        return context

    def get_success_url(self):
        return self.get_next_url()


class ProductCreateView(PermissionRequiredMixin, SuccessMessageMixin, NextUrlMixin, CreateView):
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


class ProductUpdateView(PermissionRequiredMixin, SuccessMessageMixin, NextUrlMixin, UpdateView):
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

        marca_id = self.request.GET.get("marca", "").strip()
        if marca_id:
            queryset = queryset.filter(marca_id=marca_id)

        linea_id = self.request.GET.get("linea", "").strip()
        if linea_id:
            queryset = queryset.filter(linea_id=linea_id)

        categoria_id = self.request.GET.get("categoria", "").strip()
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)

        clase_id = self.request.GET.get("clase", "").strip()
        if clase_id:
            queryset = queryset.filter(clase_id=clase_id)

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
        context["marca_id"] = self.request.GET.get("marca", "").strip()
        context["linea_id"] = self.request.GET.get("linea", "").strip()
        context["categoria_id"] = self.request.GET.get("categoria", "").strip()
        context["clase_id"] = self.request.GET.get("clase", "").strip()
        context["marcas"] = Marca.objects.filter(is_active=True).order_by("nombre")
        context["lineas"] = Linea.objects.filter(is_active=True).order_by("nombre")
        context["categorias"] = Categoria.objects.filter(is_active=True).order_by("nombre")
        context["clases"] = Clase.objects.filter(is_active=True).order_by("nombre")
        return context
