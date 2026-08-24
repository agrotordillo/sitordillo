from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from apps.compras.models import OrdenCompra
from apps.pagos.forms import GenerarCuentaForm
from apps.pagos.models import CuentaPorPagar
from apps.pagos.services import generar_cuenta_por_pagar


class CuentaPorPagarListView(ListView):
    model = CuentaPorPagar
    template_name = "pagos/cuenta_list.html"
    context_object_name = "cuentas"
    extra_context = {"active_module": "purchases"}

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("orden_compra", "orden_compra__proveedor")
            .prefetch_related("pagos")
            .order_by(
                "orden_compra__proveedor__nombre_comercial",
                "orden_compra__proveedor__nombre_fiscal",
                "orden_compra__proveedor_id",
                "fecha_vencimiento",
            )
        )


def generar_cuenta_view(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)

    if hasattr(orden, "cuenta_por_pagar"):
        messages.info(request, "Esta orden de compra ya tiene una cuenta por pagar generada.")
        return redirect("compras:orden-list")

    if orden.estatus not in (OrdenCompra.Estatus.PARCIAL, OrdenCompra.Estatus.RECIBIDA):
        messages.error(request, "Solo se puede generar una cuenta por pagar de una orden ya recibida.")
        return redirect("compras:orden-list")

    if request.method == "POST":
        form = GenerarCuentaForm(request.POST)
        if form.is_valid():
            try:
                generar_cuenta_por_pagar(
                    orden,
                    fecha_emision=form.cleaned_data["fecha_emision"],
                    observaciones=form.cleaned_data["observaciones"],
                )
                messages.success(request, "Cuenta por pagar generada correctamente.")
                return redirect("compras:orden-list")
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = GenerarCuentaForm(initial={"fecha_emision": timezone.localdate()})

    return render(
        request,
        "pagos/generar_cuenta_form.html",
        {"orden": orden, "form": form, "active_module": "purchases"},
    )
