from decimal import Decimal

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

from apps.compras.models import OrdenCompra
from apps.compras.forms import CargarCFDIForm, OrdenCompraForm, OrdenCompraDetalleFormSet
from apps.compras.services import CFDIImportError, importar_cfdi_compra
from apps.pagos.models import Pago


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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context


class OrdenCompraCreateView(PermissionRequiredMixin, CreateView):
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
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
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
        ver _resincronizar_cuenta_por_pagar-, 3) reactivar el/los pago(s)
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

    def _resincronizar_cuenta_por_pagar(self, orden):
        """El monto_total de la cuenta por pagar es una foto tomada al
        generarla (ver generar_cuenta_por_pagar) y nunca se actualiza solo;
        cada vez que se edita la orden hay que resincronizarlo con el
        total real, o quedaría desfasado (justo lo que este candado busca
        evitar). No hace nada si la orden todavía no tiene cuenta
        generada."""
        if not hasattr(orden, "cuenta_por_pagar"):
            return
        cuenta = orden.cuenta_por_pagar
        nuevo_total = orden.total.quantize(Decimal("0.01"))
        if cuenta.monto_total != nuevo_total:
            cuenta.monto_total = nuevo_total
            cuenta.full_clean()
            cuenta.save(update_fields=["monto_total"])
        cuenta.actualizar_estatus()

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
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            self._resincronizar_cuenta_por_pagar(self.object)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la orden de compra. Revisa los campos.")
        return super().form_invalid(form)
