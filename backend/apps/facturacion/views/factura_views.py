from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.scoping import almacenes_visibles
from apps.fiscal.models import MetodoPago
from apps.products.models import Turno
from apps.ventas.models import Venta
from apps.facturacion.facturama_client import FacturamaError
from apps.facturacion.forms import GenerarFacturaForm
from apps.facturacion.models import Factura, FacturaGlobal
from apps.facturacion.factura_service import (
    cancelar_factura,
    generar_factura,
    generar_factura_global,
    liberar_timbrado,
    obtener_pdf,
    obtener_xml,
    timbrar_factura,
    timbrar_factura_global,
    ventas_elegibles_para_global,
)


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
    if venta.es_remision:
        messages.error(request, "Esta venta es una remisión; nunca se le genera factura.")
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
            except ERRORES_DE_NEGOCIO as e:
                for mensaje in mensajes_de_error(e):
                    form.add_error(None, mensaje)
            else:
                messages.success(request, f"Factura {factura.serie_folio} generada en borrador.")
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
    # El servicio valida el estatus con la fila bloqueada (ya timbrada, en
    # proceso, cancelada): no basta con que el botón no se muestre.
    try:
        factura, _ = timbrar_factura(factura)
    except ERRORES_DE_NEGOCIO as e:
        for mensaje in mensajes_de_error(e):
            messages.error(request, mensaje)
    except FacturamaError as e:
        messages.error(request, f"No se pudo timbrar la factura: {e}")
    else:
        messages.success(request, f"Factura {factura.serie_folio} timbrada correctamente.")
    return redirect("facturacion:factura-list")


# Liberar un timbrado sin confirmar es la contraparte de "Cancelar": quien
# lo hace asegura que el CFDI no existe en Facturama, así que va con el
# mismo permiso, exclusivo del Administrador.
@permission_required("facturacion.delete_factura", raise_exception=True)
def liberar_timbrado_factura_view(request, pk):
    factura = get_object_or_404(_facturas_visibles(request.user), pk=pk)
    if request.method == "POST":
        try:
            liberar_timbrado(Factura, factura)
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(request, mensaje)
        else:
            messages.success(request, f"Factura {factura.serie_folio} liberada: ya se puede volver a timbrar.")
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
    except ERRORES_DE_NEGOCIO as e:
        for mensaje in mensajes_de_error(e):
            messages.error(request, mensaje)
    except FacturamaError as e:
        messages.error(request, f"No se pudo cancelar la factura: {e}")
    else:
        messages.success(request, f"Factura {factura.serie_folio} cancelada.")
    return redirect("facturacion:factura-list")


@permission_required("facturacion.view_factura", raise_exception=True)
def factura_pdf_view(request, pk):
    factura = get_object_or_404(_facturas_visibles(request.user), pk=pk)
    try:
        contenido = obtener_pdf(factura)
    except (ValueError, FacturamaError) as e:
        messages.error(request, f"No se pudo obtener el PDF: {e}")
        return redirect("facturacion:factura-list")
    response = HttpResponse(contenido, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{factura.serie_folio}.pdf"'
    return response


@permission_required("facturacion.view_factura", raise_exception=True)
def factura_xml_view(request, pk):
    factura = get_object_or_404(_facturas_visibles(request.user), pk=pk)
    try:
        contenido = obtener_xml(factura)
    except (ValueError, FacturamaError) as e:
        messages.error(request, f"No se pudo obtener el XML: {e}")
        return redirect("facturacion:factura-list")
    response = HttpResponse(contenido, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{factura.serie_folio}.xml"'
    return response


# --- Factura global (cierre fiscal de "Público en general" por turno) ----

def _facturas_globales_visibles(user):
    queryset = FacturaGlobal.objects.select_related("turno__punto_venta__almacen")
    visibles = almacenes_visibles(user)
    if visibles is not None:
        queryset = queryset.filter(turno__punto_venta__almacen__in=visibles)
    return queryset


class FacturaGlobalListView(PermissionRequiredMixin, ListView):
    permission_required = "facturacion.view_facturaglobal"
    model = FacturaGlobal
    template_name = "facturacion/factura_global_list.html"
    context_object_name = "facturas_globales"
    extra_context = {"active_module": "sales"}

    def get_queryset(self):
        return _facturas_globales_visibles(self.request.user)


# "Ventas y Caja" tiene add+change de FacturaGlobal (a diferencia de
# Factura, donde solo "Facturación"/Administrador completan el timbrado):
# el cajero queda obligado a cerrar fiscalmente su propio turno ahí mismo,
# no puede depender de que alguien más lo haga después (ver
# accounts/migrations, grupo "Ventas y Caja").
@permission_required("facturacion.add_facturaglobal", raise_exception=True)
def generar_factura_global_view(request, turno_pk):
    turnos_qs = Turno.objects.select_related("punto_venta__almacen", "usuario")
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        turnos_qs = turnos_qs.filter(punto_venta__almacen__in=visibles)
    turno = get_object_or_404(turnos_qs, pk=turno_pk)

    if hasattr(turno, "factura_global"):
        return redirect("facturacion:factura-global-detalle", pk=turno.factura_global.pk)

    ventas = list(ventas_elegibles_para_global(turno).prefetch_related("detalles__producto"))
    if not ventas:
        messages.info(request, "No hay ventas a Público en general sin facturar en este turno.")
        return redirect("products:turno-list")

    if request.method == "POST":
        pue = MetodoPago.objects.filter(clave="PUE").first()
        if not pue:
            messages.error(request, "Falta el catálogo de método de pago PUE; contacta a soporte.")
        else:
            try:
                factura_global = generar_factura_global(
                    turno, metodo_pago=pue, observaciones=request.POST.get("observaciones", "")
                )
            except ERRORES_DE_NEGOCIO as e:
                for mensaje in mensajes_de_error(e):
                    messages.error(request, mensaje)
                return redirect("products:turno-list")
            try:
                factura_global, _ = timbrar_factura_global(factura_global)
            except (*ERRORES_DE_NEGOCIO, FacturamaError) as e:
                detalle = str(e) if isinstance(e, FacturamaError) else " ".join(mensajes_de_error(e))
                messages.error(
                    request,
                    f"La factura global {factura_global.serie_folio} quedó generada pero "
                    f"no se pudo timbrar: {detalle}. Revisa su detalle.",
                )
                return redirect("facturacion:factura-global-detalle", pk=factura_global.pk)
            messages.success(request, f"Factura global {factura_global.serie_folio} generada y timbrada.")
            return redirect("facturacion:factura-global-detalle", pk=factura_global.pk)

    return render(
        request,
        "facturacion/generar_factura_global_form.html",
        {"turno": turno, "ventas": ventas, "total": sum((v.total for v in ventas), Decimal("0.00")), "active_module": "sales"},
    )


@permission_required("facturacion.view_facturaglobal", raise_exception=True)
def factura_global_detalle_view(request, pk):
    factura_global = get_object_or_404(
        _facturas_globales_visibles(request.user).select_related("turno__punto_venta__almacen", "metodo_pago"),
        pk=pk,
    )
    return render(
        request,
        "facturacion/factura_global_detalle.html",
        {"factura_global": factura_global, "active_module": "sales"},
    )


@permission_required("facturacion.change_facturaglobal", raise_exception=True)
def reintentar_timbrado_global_view(request, pk):
    factura_global = get_object_or_404(_facturas_globales_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("facturacion:factura-global-detalle", pk=pk)
    try:
        timbrar_factura_global(factura_global)
    except ERRORES_DE_NEGOCIO as e:
        for mensaje in mensajes_de_error(e):
            messages.error(request, mensaje)
    except FacturamaError as e:
        messages.error(request, f"No se pudo timbrar la factura global: {e}")
    else:
        messages.success(request, "Factura global timbrada correctamente.")
    return redirect("facturacion:factura-global-detalle", pk=pk)


# Mismo criterio que liberar_timbrado_factura_view: exclusivo del
# Administrador (ningún grupo tiene delete_facturaglobal).
@permission_required("facturacion.delete_facturaglobal", raise_exception=True)
def liberar_timbrado_global_view(request, pk):
    factura_global = get_object_or_404(_facturas_globales_visibles(request.user), pk=pk)
    if request.method == "POST":
        try:
            liberar_timbrado(FacturaGlobal, factura_global)
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(request, mensaje)
        else:
            messages.success(request, "Factura global liberada: ya se puede volver a timbrar.")
    return redirect("facturacion:factura-global-detalle", pk=pk)


@permission_required("facturacion.view_facturaglobal", raise_exception=True)
def factura_global_pdf_view(request, pk):
    factura_global = get_object_or_404(_facturas_globales_visibles(request.user), pk=pk)
    try:
        contenido = obtener_pdf(factura_global)
    except (ValueError, FacturamaError) as e:
        messages.error(request, f"No se pudo obtener el PDF: {e}")
        return redirect("facturacion:factura-global-detalle", pk=pk)
    response = HttpResponse(contenido, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{factura_global.serie_folio}.pdf"'
    return response


@permission_required("facturacion.view_facturaglobal", raise_exception=True)
def factura_global_xml_view(request, pk):
    factura_global = get_object_or_404(_facturas_globales_visibles(request.user), pk=pk)
    try:
        contenido = obtener_xml(factura_global)
    except (ValueError, FacturamaError) as e:
        messages.error(request, f"No se pudo obtener el XML: {e}")
        return redirect("facturacion:factura-global-detalle", pk=pk)
    response = HttpResponse(contenido, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{factura_global.serie_folio}.xml"'
    return response
