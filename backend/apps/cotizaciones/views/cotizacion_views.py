from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.core.scoping import almacenes_visibles
from apps.cotizaciones.models import Cotizacion, CotizacionDetalle
from apps.cotizaciones.forms import CotizacionForm, CotizacionDetalleFormSet
from apps.cotizaciones.pdf import generar_pdf_cotizacion
from apps.products.services import fijar_precios_autorizados, turno_abierto_de


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

    def dispatch(self, request, *args, **kwargs):
        # Igual que en Ventas: la sucursal (y el punto de venta, que ya
        # determina el folio) ya no los elige mostrador, se toman del
        # turno propio y abierto de quien levanta la cotización -sin uno
        # abierto no hay de dónde sacarlos, así que tampoco tiene caso
        # dejarlo entrar a la pantalla-.
        self.turno = turno_abierto_de(request.user)
        if self.turno is None:
            messages.error(request, "No tienes un turno abierto. Ábrelo antes de levantar una cotización.")
            return redirect("products:turno-list")
        self.almacen = self.turno.punto_venta.almacen
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.almacen = self.almacen
        form.instance.punto_venta = self.turno.punto_venta
        form.instance.turno = self.turno
        return form

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = CotizacionDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = CotizacionDetalleFormSet(instance=self.object, prefix="detalles")
        data["turno"] = self.turno
        data["almacen"] = self.almacen
        return data

    def form_valid(self, form):
        formset = CotizacionDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        # El precio de una cotización tampoco lo captura mostrador (misma
        # regla que en Ventas): se resuelve con la lista de precios del
        # cliente y la sucursal de la cotización, ignorando lo que haya
        # llegado en el POST.
        fijar_precios_autorizados(
            formset, form.cleaned_data.get("cliente"), self.almacen,
            CotizacionDetalle.Estrategia.FIFO,
        )

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

        # El precio de una cotización tampoco lo captura mostrador (misma
        # regla que en Ventas): se resuelve con la lista de precios del
        # cliente y la sucursal de la cotización, ignorando lo que haya
        # llegado en el POST.
        fijar_precios_autorizados(
            formset, form.cleaned_data.get("cliente"), form.instance.almacen,
            CotizacionDetalle.Estrategia.FIFO,
        )

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


class CotizacionPDFView(PermissionRequiredMixin, DetailView):
    """PDF formal para el cliente que pidió la cotización. Deja de ofrecerse
    en cuanto la cotización se convierte a venta (ver la plantilla de lista,
    donde el enlace ya no aparece para las convertidas)."""

    permission_required = "cotizaciones.view_cotizacion"
    model = Cotizacion

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("cliente", "almacen", "punto_venta")
            .prefetch_related("detalles__producto__unidad_medida")
        )
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset

    def get(self, request, *args, **kwargs):
        from apps.facturacion.models import Empresa

        self.object = self.get_object()
        if self.object.estatus != Cotizacion.Estatus.ABIERTA:
            messages.error(
                request, "Esta cotización ya fue convertida a venta; ya no se puede generar su PDF.",
            )
            return HttpResponseRedirect(reverse_lazy("cotizaciones:cotizacion-list"))

        pdf_bytes = generar_pdf_cotizacion(self.object, empresa=Empresa.objects.first())
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{self.object.numero_documento}.pdf"'
        return response
