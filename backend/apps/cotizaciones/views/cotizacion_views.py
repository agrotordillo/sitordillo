from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.core.scoping import almacenes_visibles
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.forms import CotizacionForm, CotizacionDetalleFormSet


class CotizacionListView(PermissionRequiredMixin, ListView):
    permission_required = "cotizaciones.view_cotizacion"
    model = Cotizacion
    template_name = "cotizaciones/cotizacion_list.html"
    context_object_name = "cotizaciones"
    extra_context = {"active_module": "quotes"}

    def get_queryset(self):
        queryset = super().get_queryset().select_related("cliente", "almacen", "venta").prefetch_related("detalles")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset


class CotizacionCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "cotizaciones.add_cotizacion"
    model = Cotizacion
    form_class = CotizacionForm
    template_name = "cotizaciones/cotizacion_form.html"
    success_url = reverse_lazy("cotizaciones:cotizacion-list")
    success_message = "Cotización registrada correctamente."
    extra_context = {"active_module": "quotes"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = CotizacionDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = CotizacionDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = CotizacionDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la cotización.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar la cotización. Revisa los campos.")
        return super().form_invalid(form)


class CotizacionUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "cotizaciones.change_cotizacion"
    model = Cotizacion
    form_class = CotizacionForm
    template_name = "cotizaciones/cotizacion_form.html"
    success_url = reverse_lazy("cotizaciones:cotizacion-list")
    success_message = "Cotización actualizada correctamente."
    extra_context = {"active_module": "quotes"}

    def get_queryset(self):
        queryset = super().get_queryset()
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estatus != Cotizacion.Estatus.ABIERTA:
            messages.error(
                request,
                "Solo se puede editar una cotización abierta; esta ya fue convertida a venta.",
            )
            return HttpResponseRedirect(reverse_lazy("cotizaciones:cotizacion-list"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = CotizacionDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = CotizacionDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = CotizacionDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la cotización.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la cotización. Revisa los campos.")
        return super().form_invalid(form)
