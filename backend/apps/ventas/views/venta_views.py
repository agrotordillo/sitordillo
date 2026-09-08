from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from apps.core.scoping import almacenes_visibles
from apps.products.models import Turno
from apps.ventas.models import Venta
from apps.ventas.forms import VentaForm, VentaDetalleFormSet
from apps.cobros.services import generar_cuenta_por_cobrar
from apps.ventas.services import (
    procesar_lineas_venta,
    validar_stock_disponible,
    validar_turno_abierto,
    validar_venta_a_credito,
)


class VentaListView(PermissionRequiredMixin, ListView):
    permission_required = "ventas.view_venta"
    model = Venta
    template_name = "ventas/venta_list.html"
    context_object_name = "ventas"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        queryset = super().get_queryset().select_related("cliente", "almacen").prefetch_related("detalles")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset


class VentaCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "ventas.add_venta"
    model = Venta
    form_class = VentaForm
    template_name = "ventas/venta_form.html"
    success_url = reverse_lazy("ventas:venta-list")
    success_message = "Venta registrada correctamente."
    extra_context = {"active_module": "sales"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = VentaDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = VentaDetalleFormSet(instance=self.object, prefix="detalles")

        # Aviso previo (no bloquea cargar el formulario, solo informa antes
        # de que el cajero llene todo y se tope con el error hasta enviar):
        # de las sucursales que puede elegir, en cuáles el usuario actual
        # NO tiene su propio turno abierto -ver validar_turno_abierto, que
        # exige que sea el mismo usuario, no que la sucursal tenga
        # cualquier turno abierto por alguien más.
        almacenes = list(data["form"].fields["almacen"].queryset)
        con_turno_propio_abierto = set(
            Turno.objects.filter(
                punto_venta__almacen__in=almacenes, usuario=self.request.user, estatus=Turno.Estatus.ABIERTO
            ).values_list("punto_venta__almacen_id", flat=True)
        )
        data["sucursales_sin_turno"] = [a for a in almacenes if a.pk not in con_turno_propio_abierto]
        return data

    def form_valid(self, form):
        formset = VentaDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        almacen = form.cleaned_data["almacen"]

        error_turno = validar_turno_abierto(almacen, self.request.user)
        if error_turno:
            form.add_error(None, error_turno)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            (cd["producto"], cd["cantidad"], cd["estrategia_salida"])
            for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la venta.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        errores_stock = validar_stock_disponible(almacen, lineas)
        if errores_stock:
            for error in errores_stock:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        try:
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                # La venta ya tiene su total real (self.object.total, suma
                # de los detalles recién guardados): aquí, no antes, es
                # donde se puede validar el crédito con el monto exacto.
                error_credito = validar_venta_a_credito(
                    self.object.cliente, self.object.forma_pago, self.object.total
                )
                if error_credito:
                    raise ValueError(error_credito)
                procesar_lineas_venta(self.object)
                if self.object.forma_pago.clave == Venta.CLAVE_CREDITO:
                    generar_cuenta_por_cobrar(self.object)
        except ValueError as e:
            form.add_error(None, str(e))
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar la venta. Revisa los campos.")
        return super().form_invalid(form)
