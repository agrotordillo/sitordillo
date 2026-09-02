from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.scoping import almacenes_visibles
from apps.inventario.forms import ConversionForm, RecetaConversionForm
from apps.inventario.models import Conversion, RecetaConversion
from apps.inventario.services import registrar_conversion


# Catálogo de recetas: configuración estructural (a qué equivale convertir un
# producto en otro), no una capacidad operativa del día a día -por eso no
# está en ningún grupo, igual que CentroCosto o los catálogos de products.
class RecetaConversionListView(PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_recetaconversion"
    model = RecetaConversion
    template_name = "inventario/receta_conversion_list.html"
    context_object_name = "recetas"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        return super().get_queryset().select_related("producto_origen", "producto_destino")


class RecetaConversionCreateView(PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "inventario.add_recetaconversion"
    model = RecetaConversion
    form_class = RecetaConversionForm
    template_name = "inventario/receta_conversion_form.html"
    success_url = reverse_lazy("inventario:receta-conversion-list")
    success_message = "Receta de conversión creada correctamente."
    extra_context = {"active_module": "warehouses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la receta. Revisa los campos.")
        return super().form_invalid(form)


class RecetaConversionUpdateView(PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "inventario.change_recetaconversion"
    model = RecetaConversion
    form_class = RecetaConversionForm
    template_name = "inventario/receta_conversion_form.html"
    success_url = reverse_lazy("inventario:receta-conversion-list")
    success_message = "Receta de conversión actualizada correctamente."
    extra_context = {"active_module": "warehouses"}

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la receta. Revisa los campos.")
        return super().form_invalid(form)


class ConversionListView(PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_conversion"
    model = Conversion
    template_name = "inventario/conversion_list.html"
    context_object_name = "conversiones"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("almacen", "receta__producto_origen", "receta__producto_destino")
        )
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset


@permission_required("inventario.add_conversion", raise_exception=True)
def crear_conversion_view(request):
    if request.method == "POST":
        form = ConversionForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                conversion = registrar_conversion(
                    receta=form.cleaned_data["receta"],
                    almacen=form.cleaned_data["almacen"],
                    cantidad_origen=form.cleaned_data["cantidad_origen"],
                    fecha=form.cleaned_data["fecha"],
                    observaciones=form.cleaned_data["observaciones"],
                )
            except ValueError as e:
                form.add_error(None, str(e))
            else:
                messages.success(
                    request,
                    f"Conversión {conversion.folio} registrada: {conversion.cantidad_destino_generada} "
                    f"{conversion.receta.producto_destino.nombre} generadas.",
                )
                return redirect("inventario:conversion-list")
    else:
        form = ConversionForm(initial={"fecha": timezone.localdate()}, user=request.user)

    return render(
        request,
        "inventario/conversion_form.html",
        {"form": form, "active_module": "warehouses"},
    )
