from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from apps.core.scoping import almacenes_visibles
from apps.fiscal.models import MetodoPago
from apps.ventas.models import Venta
from apps.facturacion.facturama_client import FacturamaError
from apps.facturacion.forms import GenerarFacturaForm
from apps.facturacion.models import Factura
from apps.facturacion.factura_service import cancelar_factura, generar_factura, timbrar_factura


def _facturas_visibles(user):
    queryset = Factura.objects.all()
    visibles = almacenes_visibles(user)
    if visibles is not None:
        queryset = queryset.filter(venta__almacen__in=visibles)
    return queryset


class FacturaListView(PermissionRequiredMixin, ListView):
    permission_required = "facturacion.view_factura"
    model = Factura
    template_name = "facturacion/factura_list.html"
    context_object_name = "facturas"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return _facturas_visibles(self.request.user).select_related("venta", "venta__cliente")


@permission_required("facturacion.add_factura", raise_exception=True)
def generar_factura_view(request, venta_pk):
    ventas_qs = Venta.objects.all()
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        ventas_qs = ventas_qs.filter(almacen__in=visibles)
    venta = get_object_or_404(ventas_qs, pk=venta_pk)

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


# "Facturación" tiene change_factura (agregado en
# accounts/migrations/0004_facturacion_change_factura.py) para poder
# completar el timbrado, a diferencia de delete_factura (cancelar), que
# sigue siendo exclusivo del Administrador.
@permission_required("facturacion.change_factura", raise_exception=True)
def timbrar_factura_view(request, pk):
    factura = get_object_or_404(_facturas_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("facturacion:factura-list")
    try:
        timbrar_factura(factura)
        messages.success(request, f"Factura {factura.serie}-{factura.numero_folio} timbrada correctamente.")
    except FacturamaError as e:
        messages.error(request, f"No se pudo timbrar la factura: {e}")
    return redirect("facturacion:factura-list")


# "Cancelar" reutiliza el permiso delete_factura como semántica de
# "anular" (regla de negocio: cancelar es exclusivo del Administrador,
# ningún grupo tiene delete_factura a propósito).
@permission_required("facturacion.delete_factura", raise_exception=True)
def cancelar_factura_view(request, pk):
    factura = get_object_or_404(_facturas_visibles(request.user), pk=pk)
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
