import base64

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView

from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.filtros_fecha import FiltroFechaMixin
from apps.core.scoping import almacenes_visibles
from apps.products.services import turno_abierto_de
from apps.ventas.forms import RetiroEfectivoForm
from apps.ventas.models import RetiroEfectivo
from apps.ventas.services import efectivo_del_turno


def _retiros_visibles(usuario):
    queryset = RetiroEfectivo.objects.select_related(
        "turno", "turno__punto_venta", "turno__punto_venta__almacen", "turno__usuario"
    )
    visibles = almacenes_visibles(usuario)
    if visibles is not None:
        queryset = queryset.filter(turno__punto_venta__almacen__in=visibles)
    return queryset


class RetiroEfectivoListView(FiltroFechaMixin, PermissionRequiredMixin, ListView):
    """Retiros de efectivo del día (ver FiltroFechaMixin), con su total por
    tipo (gasto / caja fuerte)."""

    permission_required = "ventas.view_retiroefectivo"
    template_name = "ventas/retiro_list.html"
    context_object_name = "retiros"
    extra_context = {"active_module": "sales"}
    filtro_fecha_campo = "fecha"

    def get_queryset(self):
        return self.aplicar_filtro_fecha(_retiros_visibles(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        por_tipo = {}
        for retiro in context["retiros"]:
            clave = retiro.get_tipo_display()
            por_tipo[clave] = por_tipo.get(clave, 0) + retiro.monto
        context["por_tipo"] = por_tipo
        context["total_retiros"] = sum(por_tipo.values())
        return context


@permission_required("ventas.add_retiroefectivo", raise_exception=True)
def retiro_efectivo_create_view(request):
    """El cajero saca efectivo de la caja de su propio turno abierto, sin
    autorización de nadie más (igual que en scvweb). El efectivo en caja
    se muestra solo como referencia, no limita el monto: no hay fondo
    inicial registrado, así que puede haber más efectivo del que se cobró."""
    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    turno = turno_abierto_de(request.user, solo_cobro=True)
    if turno is None:
        messages.error(request, "Abre tu turno de caja antes de retirar efectivo.")
        return redirect("products:turno-list")

    if request.method == "POST":
        form = RetiroEfectivoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    envio = reservar_envio(request)
                    retiro = form.save(commit=False)
                    retiro.turno = turno
                    retiro.full_clean()
                    retiro.save()
                    url_ticket = reverse("ventas:retiro-ticket", args=[retiro.pk])
                    envio.completar(url_ticket)
            except EnvioDuplicado as duplicado:
                return respuesta_envio_duplicado(request, duplicado.url_resultado, "ventas:retiro-list")
            except ERRORES_DE_NEGOCIO as e:
                for mensaje in mensajes_de_error(e):
                    form.add_error(None, mensaje)
            else:
                messages.success(request, f"Retiro {retiro.folio} registrado por ${retiro.monto}.")
                return redirect(url_ticket)
    else:
        form = RetiroEfectivoForm()

    return render(
        request,
        "ventas/retiro_form.html",
        {
            "form": form,
            "turno": turno,
            "efectivo": efectivo_del_turno(turno),
            "active_module": "sales",
        },
    )


class RetiroEfectivoTicketView(PermissionRequiredMixin, DetailView):
    """Comprobante del retiro en la impresora de caja (QZ Tray, ver
    venta-ticket.js), o impresión normal del navegador si la sucursal no
    tiene impresora configurada -igual que el ticket de venta-."""

    permission_required = "ventas.view_retiroefectivo"
    template_name = "ventas/retiro_ticket.html"
    context_object_name = "retiro"

    def get_queryset(self):
        return _retiros_visibles(self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        RetiroEfectivo.objects.filter(pk=self.object.pk).update(veces_impreso=F("veces_impreso") + 1)
        self.object.refresh_from_db(fields=["veces_impreso"])
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_context_data(self, **kwargs):
        from apps.facturacion.models import Empresa
        from apps.ventas.ticket import construir_ticket_retiro

        context = super().get_context_data(**kwargs)
        empresa = Empresa.objects.first()
        context["empresa"] = empresa
        almacen = self.object.turno.punto_venta.almacen
        if almacen.impresora_nombre:
            context["ticket_data"] = {
                "printer": almacen.impresora_nombre,
                "data": base64.b64encode(construir_ticket_retiro(self.object, empresa)).decode("ascii"),
                "auto": almacen.imprimir_ticket_automatico,
            }
        return context
