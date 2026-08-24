from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.inventario.forms import CorregirLoteForm, ReportarMermaForm
from apps.inventario.models import Lote
from apps.inventario.services import corregir_recepcion, registrar_merma_recepcion


def corregir_lote_view(request, pk):
    lote = get_object_or_404(Lote, pk=pk)

    if lote.cantidad_disponible <= 0:
        messages.error(request, "Este lote ya no tiene existencia disponible para corregir.")
        return redirect("inventario:lote-list")

    if request.method == "POST":
        form = CorregirLoteForm(request.POST, lote=lote)
        if form.is_valid():
            try:
                corregir_recepcion(
                    lote,
                    form.cleaned_data["cantidad"],
                    form.cleaned_data["producto"],
                    motivo=form.cleaned_data["motivo"],
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Recepción corregida correctamente.")
                return redirect("inventario:lote-list")
    else:
        form = CorregirLoteForm(lote=lote)

    return render(
        request,
        "inventario/corregir_lote_form.html",
        {"lote": lote, "form": form, "active_module": "warehouses"},
    )


def reportar_merma_view(request, pk):
    lote = get_object_or_404(Lote, pk=pk)

    if lote.cantidad_disponible <= 0:
        messages.error(request, "Este lote ya no tiene existencia disponible para dar de baja.")
        return redirect("inventario:lote-list")

    if request.method == "POST":
        form = ReportarMermaForm(request.POST, lote=lote)
        if form.is_valid():
            try:
                registrar_merma_recepcion(
                    lote,
                    form.cleaned_data["cantidad"],
                    motivo=form.cleaned_data["motivo"],
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Merma registrada correctamente.")
                return redirect("inventario:lote-list")
    else:
        form = ReportarMermaForm(lote=lote)

    return render(
        request,
        "inventario/reportar_merma_form.html",
        {"lote": lote, "form": form, "active_module": "warehouses"},
    )
