from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.products.forms import PuntoVentaForm
from apps.products.models import Almacen, PuntoVenta


class PuntoVentaListView(ListView):
    model = PuntoVenta
    template_name = "warehouses/punto_venta_list.html"
    context_object_name = "puntos_venta"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        self.almacen = get_object_or_404(Almacen, pk=self.kwargs["almacen_id"])
        return super().get_queryset().filter(almacen=self.almacen)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["almacen"] = self.almacen
        return context


class PuntoVentaCreateView(SuccessMessageMixin, CreateView):
    model = PuntoVenta
    form_class = PuntoVentaForm
    template_name = "warehouses/punto_venta_form.html"
    success_message = "Punto de venta creado correctamente."
    extra_context = {"active_module": "warehouses"}

    def dispatch(self, request, *args, **kwargs):
        self.almacen = get_object_or_404(Almacen, pk=kwargs["almacen_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        # El almacén se fija aquí (no es un campo del form) para que ya esté
        # en la instancia cuando Django valide unicidad de (almacen, codigo);
        # asignarlo en form_valid() es demasiado tarde y deja pasar duplicados
        # hasta el IntegrityError de la base de datos.
        form = super().get_form(form_class)
        form.instance.almacen = self.almacen
        return form

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el punto de venta. Revisa los campos.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["almacen"] = self.almacen
        return context

    def get_success_url(self):
        return reverse_lazy("products:punto-venta-list", kwargs={"almacen_id": self.almacen.pk})


class PuntoVentaUpdateView(SuccessMessageMixin, UpdateView):
    model = PuntoVenta
    form_class = PuntoVentaForm
    template_name = "warehouses/punto_venta_form.html"
    success_message = "Punto de venta actualizado correctamente."
    extra_context = {"active_module": "warehouses"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["almacen"] = self.object.almacen
        return context

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el punto de venta. Revisa los campos.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("products:punto-venta-list", kwargs={"almacen_id": self.object.almacen_id})
