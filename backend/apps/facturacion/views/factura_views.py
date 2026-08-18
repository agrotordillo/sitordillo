from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from apps.fiscal.models import MetodoPago
from apps.ventas.models import Venta
from apps.facturacion.facturama_client import FacturamaError
from apps.facturacion.forms import GenerarFacturaForm
from apps.facturacion.models import Factura
from apps.facturacion.factura_service import cancelar_factura, generar_factura, timbrar_factura


class FacturaListView(ListView):
    model = Factura
    template_name = "facturacion/factura_list.html"
    context_object_name = "facturas"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return super().get_queryset().select_related("venta", "venta__cliente")


def generar_factura_view(request, venta_pk):
    venta = get_object_or_404(Venta, pk=venta_pk)

    if hasattr(venta, "factura"):
        messages.info(request, "Esta venta ya tiene una factura generada.")
        return redirect("ventas:venta-list")

    if request.method == "POST":
        form = GenerarFacturaForm(request.POST)
        if form.is_valid():
            try:
                factura = generar_factura(
                    venta,
                    uso_cfdi=form.cleaned_data["uso_cfdi"],
                    metodo_pago=form.cleaned_data["metodo_pago"],
                    serie=form.cleaned_data["serie"] or None,
                    observaciones=form.cleaned_data["observaciones"],
                )
            except ValueError as e:
                form.add_error(None, str(e))
            except ValidationError as e:
                mensajes = e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages}
                for field, errores in mensajes.items():
                    for msg in errores:
                        form.add_error(None, msg)
            else:
                messages.success(request, f"Factura {factura.serie}-{factura.numero_folio} generada en borrador.")
                return redirect("facturacion:factura-list")
    else:
        initial = {}
        if venta.cliente.uso_cfdi_id:
            initial["uso_cfdi"] = venta.cliente.uso_cfdi_id
        pue = MetodoPago.objects.filter(clave="PUE").first()
        if pue:
            initial["metodo_pago"] = pue.id
        form = GenerarFacturaForm(initial=initial)

    return render(
        request,
        "facturacion/generar_factura_form.html",
        {"venta": venta, "form": form, "active_module": "sales"},
    )


def timbrar_factura_view(request, pk):
    factura = get_object_or_404(Factura, pk=pk)
    if request.method != "POST":
        return redirect("facturacion:factura-list")
    try:
        timbrar_factura(factura)
        messages.success(request, f"Factura {factura.serie}-{factura.numero_folio} timbrada correctamente.")
    except FacturamaError as e:
        messages.error(request, f"No se pudo timbrar la factura: {e}")
    return redirect("facturacion:factura-list")


def cancelar_factura_view(request, pk):
    factura = get_object_or_404(Factura, pk=pk)
    if request.method != "POST":
        return redirect("facturacion:factura-list")
    if factura.estatus != Factura.Estatus.TIMBRADA:
        messages.error(request, "Solo se puede cancelar una factura ya timbrada.")
        return redirect("facturacion:factura-list")
    try:
        cancelar_factura(factura)
        messages.success(request, f"Factura {factura.serie}-{factura.numero_folio} cancelada.")
    except FacturamaError as e:
        messages.error(request, f"No se pudo cancelar la factura: {e}")
    return redirect("facturacion:factura-list")
