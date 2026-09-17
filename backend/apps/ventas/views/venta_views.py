from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView

from apps.core.scoping import almacenes_visibles
from apps.products.models import Turno
from apps.products.services import fijar_precios_autorizados
from apps.ventas.models import Venta, VentaDetalle
from apps.ventas.forms import VentaForm, VentaDetalleFormSet, VentaPagoFormSet
from apps.cobros.services import generar_cuenta_por_cobrar
from apps.ventas.services import (
    obtener_turno_abierto,
    procesar_lineas_venta,
    validar_pago_dividido,
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


class VentaTicketView(PermissionRequiredMixin, DetailView):
    permission_required = "ventas.view_venta"
    model = Venta
    template_name = "ventas/venta_ticket.html"
    context_object_name = "venta"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "cliente",
                "almacen",
                "forma_pago",
                "turno",
                "turno__punto_venta",
                "turno__usuario",
                "cotizacion_origen",
                "cotizacion_origen__created_by",
            )
            .prefetch_related("detalles__producto__unidad_medida", "pagos__forma_pago")
        )
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset

    def get(self, request, *args, **kwargs):
        # Cada carga de esta pantalla es un intento de impresión (automática
        # o vía el botón), así que aquí -no en get_context_data, que puede
        # llamarse más de una vez- es donde se cuenta: "Impresión: 1" la
        # primera vez, "Impresión: 2" en una reimpresión, etc.
        self.object = self.get_object()
        Venta.objects.filter(pk=self.object.pk).update(veces_impreso=F("veces_impreso") + 1)
        self.object.refresh_from_db(fields=["veces_impreso"])
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        import base64

        from apps.facturacion.models import Empresa
        from apps.ventas.ticket import construir_ticket

        context = super().get_context_data(**kwargs)
        empresa = Empresa.objects.first()
        context["empresa"] = empresa

        almacen = self.object.almacen
        if almacen.impresora_nombre:
            # Solo se arma/embebe el payload ESC/POS si la sucursal ya tiene
            # una impresora configurada -si no, el ticket se comporta igual
            # que antes (solo el botón "Imprimir ticket" con window.print).
            context["ticket_data"] = {
                "printer": almacen.impresora_nombre,
                "data": base64.b64encode(construir_ticket(self.object, empresa)).decode("ascii"),
                "auto": almacen.imprimir_ticket_automatico,
            }
        return context


class VentaCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "ventas.add_venta"
    model = Venta
    form_class = VentaForm
    template_name = "ventas/venta_form.html"
    success_message = "Venta registrada correctamente."
    extra_context = {"active_module": "sales"}

    def get_success_url(self):
        # Al terminar de registrar la venta, directo al ticket listo para
        # imprimir -no al listado-, para no obligar a un clic extra en el
        # mostrador.
        return reverse("ventas:venta-ticket", args=[self.object.pk])

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
        if "pagos_formset" not in data:
            if self.request.method == "POST":
                data["pagos_formset"] = VentaPagoFormSet(self.request.POST, instance=self.object, prefix="pagos")
            else:
                data["pagos_formset"] = VentaPagoFormSet(instance=self.object, prefix="pagos")

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
        pagos_formset = VentaPagoFormSet(self.request.POST, instance=form.instance, prefix="pagos")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))

        almacen = form.cleaned_data["almacen"]

        error_turno = validar_turno_abierto(almacen, self.request.user)
        if error_turno:
            form.add_error(None, error_turno)
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))
        form.instance.turno = obtener_turno_abierto(almacen, self.request.user)

        # El cobro se captura con una sola forma de pago, o dividido en
        # varias (ver Venta.pago_dividido) -nunca ambas-: si se dividió,
        # forma_pago se limpia aquí sin importar qué haya llegado en ese
        # campo del POST (el HTML lo oculta cuando el checkbox está
        # activo, pero eso tampoco es la garantía real).
        pago_dividido = form.cleaned_data.get("pago_dividido")
        if pago_dividido:
            form.instance.forma_pago = None
            if not pagos_formset.is_valid():
                return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))
        elif not form.cleaned_data.get("forma_pago"):
            form.add_error("forma_pago", 'Indica la forma de pago, o marca "Dividir el cobro".')
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))

        # El precio de una venta no lo captura el cajero -ni tampoco quien
        # levanta una cotización, misma regla-: se resuelve aquí con la
        # lista de precios del cliente -su "precio preferencial", o
        # "PUBLICO" si no tiene una propia- y la sucursal de la venta,
        # ignorando cualquier precio_unitario que haya llegado en el POST
        # -el campo es readonly en el HTML, pero eso no basta como
        # garantía-. Igual se fija la estrategia de salida siempre en FIFO
        # y el descuento en 0 (ver fijar_precios_autorizados).
        fijar_precios_autorizados(formset, form.cleaned_data.get("cliente"), almacen, VentaDetalle.Estrategia.FIFO)

        lineas = [
            (cd["producto"], cd["cantidad"], VentaDetalle.Estrategia.FIFO)
            for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto a la venta.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))

        errores_stock = validar_stock_disponible(almacen, lineas)
        if errores_stock:
            for error in errores_stock:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))

        try:
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                formset.save()

                if pago_dividido:
                    # El total real (self.object.total) solo se conoce
                    # hasta aquí, con los detalles ya guardados y su
                    # precio resuelto -por eso el cobro dividido se valida
                    # después de formset.save(), no antes-.
                    montos = [
                        cd["monto"]
                        for f in pagos_formset
                        if (cd := f.cleaned_data) and cd.get("forma_pago") and not cd.get("DELETE")
                    ]
                    errores_pago = validar_pago_dividido(self.object.total, montos)
                    if errores_pago:
                        raise ValueError(" ".join(errores_pago))
                    pagos_formset.instance = self.object
                    pagos_formset.save()
                elif self.object.efectivo_recibido is not None and self.object.efectivo_recibido < self.object.total:
                    # Igual que arriba: self.object.total (la suma de los
                    # detalles ya guardados) solo se conoce hasta aquí, así
                    # que esta comparación no puede vivir en Venta.clean().
                    raise ValueError("El efectivo recibido no puede ser menor que el total de la venta.")

                # La venta ya tiene su total real: aquí, no antes, es donde
                # se puede validar el crédito con el monto exacto.
                error_credito = validar_venta_a_credito(
                    self.object.cliente, self.object.forma_pago, self.object.total
                )
                if error_credito:
                    raise ValueError(error_credito)
                procesar_lineas_venta(self.object)
                if self.object.forma_pago and self.object.forma_pago.clave == Venta.CLAVE_CREDITO:
                    generar_cuenta_por_cobrar(self.object)
        except ValueError as e:
            form.add_error(None, str(e))
            return self.render_to_response(self.get_context_data(form=form, formset=formset, pagos_formset=pagos_formset))

        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible registrar la venta. Revisa los campos.")
        return super().form_invalid(form)
