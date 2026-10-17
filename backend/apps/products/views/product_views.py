from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin

from apps.core.filtros_producto import FiltrosProductoMixin
from apps.core.navegacion import url_de_regreso
from apps.products import columnas_listado
from apps.products.busqueda import buscar_productos
from apps.products.models import Producto, ProductoPrecio
from apps.products.forms import ProductForm


class NextUrlMixin:
    """Permite que "Guardar" y "Cancelar" regresen a la búsqueda/filtro
    desde donde se entró al formulario (?next=...) en vez de mandar
    siempre al listado sin filtros. El listado arma el enlace con
    ?next={{ request.get_full_path }} y el formulario reenvía ese mismo
    valor en un input oculto para que sobreviva a un reenvío por error
    de validación."""

    def get_next_url(self):
        return url_de_regreso(self.request, self.success_url)

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Para la confirmación al cambiar el costo (producto-costo-confirmar.js):
        # qué listas se recalcularían y con qué % de utilidad, para mostrar
        # el antes/después antes de guardar, y el precio general de Público
        # (por si está capturado a mano: aun así es el que toma el precio
        # de venta, ver Producto.sincronizar_precio_venta_con_publico).
        precios = (
            ProductoPrecio.objects.filter(producto=self.object)
            .select_related("lista_precio", "almacen")
            .order_by("lista_precio__orden", "almacen__nombre")
        )
        filas = []
        publico_general = None
        for precio in precios:
            es_publico_general = precio.lista_precio.nombre == "PUBLICO" and not precio.almacen_id
            if es_publico_general:
                publico_general = str(precio.precio_con_impuesto)
            if precio.utilidad_pct is None:
                continue
            filas.append({
                "lista": precio.lista_precio.nombre,
                "sucursal": precio.almacen.nombre if precio.almacen_id else "",
                "utilidad_pct": str(precio.utilidad_pct),
                "precio_actual": str(precio.precio_con_impuesto),
                "es_publico_general": es_publico_general,
            })
        context["precios_con_utilidad"] = {"filas": filas, "publico_general": publico_general}
        return context

    def form_valid(self, form):
        form.instance.recalcular_precios_lista = form.cleaned_data["actualizar_precios_lista"]
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el producto. Revisa los campos.")
        return super().form_invalid(form)


class ProductToggleActivoView(PermissionRequiredMixin, View):
    """Baja lógica: un producto nunca se elimina, solo se desactiva. Los
    buscadores de producto usados al vender, traspasar, cotizar o comprar
    ya filtran por is_active=True, así que un producto inactivo deja de
    poder elegirse en operaciones nuevas, pero se conserva íntegro en el
    historial (ventas, traspasos, kardex, etc.) ya registrado."""

    permission_required = "products.change_producto"

    def post(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        producto.is_active = not producto.is_active
        producto.save(update_fields=["is_active"])
        if producto.is_active:
            messages.success(request, f"Producto {producto.nombre} reactivado.")
        else:
            messages.success(request, f"Producto {producto.nombre} desactivado.")
        return redirect(url_de_regreso(request, reverse("products:product-list")))


def filtrar_busqueda_producto(queryset, q):
    return buscar_productos(queryset, q)


class ProductListView(FiltrosProductoMixin, PermissionRequiredMixin, ListView):
    """Las columnas (cuáles y en qué orden) y la agrupación las elige cada
    usuario con "Columnas" y "Agrupar por" (ver apps.products.columnas_listado
    y ProductListPreferenciasView)."""

    permission_required = "products.view_producto"
    model = Producto
    template_name = "products/product_list.html"
    context_object_name = "products"
    extra_context = {"active_module": "products"}
    paginate_by = 25

    def get_preferencia(self):
        if not hasattr(self, "_preferencia"):
            self._preferencia = columnas_listado.preferencia_de(self.request.user)
        return self._preferencia

    def get_queryset(self):
        self.queryset_filtrado = filtrar_busqueda_producto(
            super().get_queryset(), self.request.GET.get("q", "").strip(),
        )
        claves_columnas, claves_agrupar = self.get_preferencia()
        return columnas_listado.preparar_queryset(self.queryset_filtrado, claves_columnas, claves_agrupar)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        claves_columnas, claves_agrupar = self.get_preferencia()
        columnas = [columnas_listado.COLUMNAS[clave] for clave in claves_columnas]
        conteos = (
            columnas_listado.conteos_por_grupo(self.queryset_filtrado, claves_agrupar) if claves_agrupar else {}
        )
        filas = columnas_listado.filas_agrupadas(context["products"], claves_agrupar, conteos)
        for fila in filas:
            if not fila["es_grupo"]:
                fila["celdas"] = [(columna, columna.valor(fila["producto"])) for columna in columnas]
        context.update({
            "q": self.request.GET.get("q", "").strip(),
            "columnas": columnas,
            "filas": filas,
            "total_columnas": len(columnas) + 1,
            "muestra_contenido_aparte": "contenido" in claves_columnas,
            "agrupar": [columnas_listado.AGRUPACIONES[clave] for clave in claves_agrupar],
            "columnas_disponibles": [
                columna for clave, columna in columnas_listado.COLUMNAS.items() if clave not in claves_columnas
            ],
            "agrupar_estatico": (
                claves_agrupar[0]
                if len(claves_agrupar) == 1 and claves_agrupar[0] in columnas_listado.AGRUPACIONES_ESTATICAS
                else ""
            ),
            "agrupar_es_dinamico": bool(claves_agrupar) and not (
                len(claves_agrupar) == 1 and claves_agrupar[0] in columnas_listado.AGRUPACIONES_ESTATICAS
            ),
            "agrupaciones_estaticas": [
                columnas_listado.AGRUPACIONES[clave] for clave in columnas_listado.AGRUPACIONES_ESTATICAS
            ],
            "agrupaciones_disponibles": [
                agrupacion for clave, agrupacion in columnas_listado.AGRUPACIONES.items()
                if clave not in claves_agrupar
            ],
        })
        return context


class ProductListPreferenciasView(PermissionRequiredMixin, View):
    """Guarda lo que el usuario eligió en "Columnas" o "Agrupar por" del
    listado de Productos y regresa al listado con los mismos filtros."""

    permission_required = "products.view_producto"
    http_method_names = ["post"]

    def post(self, request):
        accion = request.POST.get("accion")
        if accion == "columnas":
            columnas_listado.guardar_preferencia(request.user, columnas=request.POST.getlist("columnas"))
        elif accion == "restablecer_columnas":
            columnas_listado.guardar_preferencia(request.user, columnas=columnas_listado.COLUMNAS_DEFAULT)
        elif accion == "agrupar":
            if request.POST.get("modo") == "dinamico":
                agrupar = request.POST.getlist("agrupar")
            else:
                estatico = request.POST.get("agrupar_estatico", "")
                agrupar = [estatico] if estatico in columnas_listado.AGRUPACIONES_ESTATICAS else []
            columnas_listado.guardar_preferencia(request.user, agrupar=agrupar)
        return redirect(url_de_regreso(request, reverse("products:product-list")))
