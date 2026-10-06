from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.compras.forms import CargarCFDIForm, OrdenCompraForm, OrdenCompraDetalleFormSet
from apps.compras.services import CFDIImportError, importar_cfdi_compra
from apps.core.envio_unico import EnvioDuplicado, EnvioUnicoMixin, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.parametros import fecha, filtrar_por_id
from apps.pagos.models import CuentaPorPagar, Pago
from apps.pagos.services import resincronizar_cuenta_por_pagar


class OrdenCompraListView(PermissionRequiredMixin, ListView):
    permission_required = "compras.view_ordencompra"
    model = OrdenCompra
    template_name = "compras/orden_compra_list.html"
    context_object_name = "ordenes"
    extra_context = {"active_module": "purchases"}
    paginate_by = 25

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("proveedor", "cuenta_por_pagar")
            .prefetch_related(
                "detalles",
                # Distinto de "cuenta_por_pagar__pagos" a secas: aquí solo
                # interesan los pagos activos, que son los que bloquean
                # "Editar" (ver OrdenCompraUpdateView._mensaje_si_tiene_pagos).
                Prefetch(
                    "cuenta_por_pagar__pagos",
                    queryset=Pago.objects.filter(is_active=True),
                    to_attr="pagos_activos",
                ),
            )
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(folio__icontains=q)
                | Q(proveedor__nombre_fiscal__icontains=q)
                | Q(proveedor__nombre_comercial__icontains=q)
                | Q(proveedor__rfc__icontains=q)
            )

        queryset = filtrar_por_id(queryset, "proveedor_id", self.request.GET.get("proveedor"))

        fecha_desde = fecha(self.request.GET.get("fecha_desde"))
        if fecha_desde:
            queryset = queryset.filter(fecha_orden__gte=fecha_desde)
        fecha_hasta = fecha(self.request.GET.get("fecha_hasta"))
        if fecha_hasta:
            queryset = queryset.filter(fecha_orden__lte=fecha_hasta)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        context["proveedor_id"] = self.request.GET.get("proveedor", "")
        context["fecha_desde"] = self.request.GET.get("fecha_desde", "")
        context["fecha_hasta"] = self.request.GET.get("fecha_hasta", "")
        return context


class OrdenCompraCreateView(PermissionRequiredMixin, EnvioUnicoMixin, CreateView):
    permission_required = "compras.add_ordencompra"
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = "compras/orden_compra_form.html"
    success_url = reverse_lazy("compras:orden-list")
    success_message = "Orden de compra creada correctamente."
    extra_context = {"active_module": "purchases"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = OrdenCompraDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = OrdenCompraDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = OrdenCompraDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        try:
            with transaction.atomic():
                envio = reservar_envio(self.request)
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                envio.completar(self.get_success_url())
        except EnvioDuplicado as duplicado:
            return respuesta_envio_duplicado(self.request, duplicado.url_resultado, self.success_url)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la orden de compra. Revisa los campos.")
        return super().form_invalid(form)


@permission_required("compras.add_ordencompra", raise_exception=True)
def cargar_cfdi_view(request):
    if request.method == "POST":
        form = CargarCFDIForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                orden, no_encontrados = importar_cfdi_compra(form.cleaned_data["archivo"])
            except CFDIImportError as exc:
                form.add_error(None, str(exc))
            except ValidationError as exc:
                mensajes = exc.messages if hasattr(exc, "messages") else [str(exc)]
                for mensaje in mensajes:
                    form.add_error(None, mensaje)
            else:
                if no_encontrados:
                    detalle = ", ".join(
                        (c["codigo"] or c["descripcion"] or "?") for c in no_encontrados
                    )
                    messages.warning(
                        request,
                        f"Se creó la orden {orden.folio} desde el CFDI, pero "
                        f"{len(no_encontrados)} producto(s) no se encontraron y no se agregaron: "
                        f"{detalle}. Agrégalos manualmente y revisa el resto antes de guardar.",
                    )
                else:
                    messages.success(
                        request,
                        f"Orden {orden.folio} creada desde el CFDI. Revisa los datos antes de guardarla.",
                    )
                return redirect("compras:orden-update", pk=orden.pk)
    else:
        form = CargarCFDIForm()

    return render(
        request,
        "compras/cargar_cfdi_form.html",
        {"form": form, "active_module": "purchases"},
    )


class OrdenCompraUpdateView(PermissionRequiredMixin, UpdateView):
    # Ojo: "change_ordencompra" solo lo tiene "Compras - Completo", no
    # "Compras - Captura" (residente) - ver la nota en
    # accounts/migrations/0003_grupos_de_capacidades.py sobre por qué esta
    # misma vista maneja tanto editar un borrador como avanzar el estatus.
    permission_required = "compras.change_ordencompra"
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = "compras/orden_compra_form.html"
    success_url = reverse_lazy("compras:orden-list")
    success_message = "Orden de compra actualizada correctamente."
    extra_context = {"active_module": "purchases"}

    def _mensaje_si_tiene_pagos(self, orden):
        """Una orden con al menos un pago ACTIVO en su cuenta por pagar no
        se puede editar directamente: el monto de la cuenta se fija como
        una foto del total de la orden al generarla (ver
        generar_cuenta_por_pagar) y no se recalcula solo, así que cambiar
        cantidades/precios con un pago ya aplicado lo dejaría sin relación
        real con lo que dice la orden.

        Para corregir una orden así (procedimiento de reversa): 1) anular
        el/los pago(s) activos de su cuenta desde "Registrar pago" -esto
        libera el candado-, 2) editar la orden -al guardar, esta vista
        resincroniza sola el monto_total de la cuenta con el nuevo total,
        ver pagos.services.resincronizar_cuenta_por_pagar-, 3) reactivar el/los pago(s)
        (o registrar uno nuevo si el monto cambió). Un pago Inactivo no
        cuenta aquí a propósito: es justo lo que permite este flujo."""
        if not hasattr(orden, "cuenta_por_pagar"):
            return None
        if not orden.cuenta_por_pagar.pagos.filter(is_active=True).exists():
            return None
        return (
            f"La orden {orden.folio} tiene pagos activos en su cuenta por pagar; "
            "anúlalos primero desde \"Registrar pago\" para poder editarla."
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        error = self._mensaje_si_tiene_pagos(self.object)
        if error:
            messages.error(request, error)
            return redirect("compras:orden-list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        error = self._mensaje_si_tiene_pagos(self.object)
        if error:
            messages.error(request, error)
            return redirect("compras:orden-list")
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = OrdenCompraDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = OrdenCompraDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = OrdenCompraDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        try:
            with transaction.atomic():
                # Mismo candado que la recepción (inventario.views.recepcion_views._recibir):
                # las reglas de B20 (estatus, no quitar, cambiar ni bajar lo
                # recibido) se decidieron con lo recibido al cargar el
                # formulario; si desde entonces entró o se corrigió una
                # recepción, ya no corresponden y no se guarda nada.
                OrdenCompra.objects.select_for_update().get(pk=self.object.pk)
                recibido_ahora = dict(
                    OrdenCompraDetalle.objects.filter(orden_compra=self.object).values_list("pk", "cantidad_recibida")
                )
                if recibido_ahora != form.recibido_al_cargar:
                    raise ValueError(
                        "Se registró una recepción de esta orden mientras la editabas. "
                        "Vuelve a abrirla para ver lo recibido y captura de nuevo tus cambios."
                    )
                # generar_cuenta_por_pagar toma el mismo candado.
                if (
                    form.cleaned_data.get("estatus") == OrdenCompra.Estatus.CANCELADA
                    and CuentaPorPagar.objects.filter(orden_compra=self.object).exists()
                ):
                    raise ValueError("No se puede cancelar una orden que ya tiene cuenta por pagar.")
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                # Con mercancía recibida el estatus no se elige: si se subió o
                # bajó la cantidad pedida, pasa a Parcial o Recibida aquí.
                self.object.actualizar_estatus_por_recepcion()
                # Cada edición puede mover el total: la cuenta por pagar (si ya
                # existe) se resincroniza aquí mismo, en la misma transacción.
                resincronizar_cuenta_por_pagar(self.object)
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(self.request, mensaje)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la orden de compra. Revisa los campos.")
        return super().form_invalid(form)
