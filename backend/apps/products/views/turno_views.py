from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView

from apps.core.parametros import id_valido
from apps.core.scoping import almacenes_visibles
from apps.facturacion.factura_service import ventas_elegibles_para_global
from apps.products.models import PuntoVenta, Turno
from apps.products.services import abrir_turno, tipos_punto_venta_de
from apps.ventas.services import resumen_turno


class TurnoListView(PermissionRequiredMixin, ListView):
    """Apertura/cierre de turno por punto de venta (ver Turno). Un usuario
    restringido solo ve y abre turnos de sus sucursales asignadas, y solo
    en el tipo de punto de venta que le da su rol: caja (Cobro) quien
    cobra ventas, mostrador (Pedido) quien levanta cotizaciones/pedidos
    (ver products.services.tipos_punto_venta_de)."""

    permission_required = "products.view_turno"
    model = Turno
    template_name = "warehouses/turno_list.html"
    context_object_name = "turnos"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset().select_related("punto_venta__almacen", "usuario")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(punto_venta__almacen__in=visibles)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        puntos_venta = PuntoVenta.objects.filter(
            is_active=True, tipo__in=tipos_punto_venta_de(self.request.user), almacen__is_active=True
        ).select_related("almacen")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            puntos_venta = puntos_venta.filter(almacen__in=visibles)
        context["puntos_venta"] = puntos_venta
        return context


@permission_required("products.view_turno", raise_exception=True)
def turno_corte_view(request, pk):
    """Corte de caja: resumen operativo de lo vendido en este turno, por
    forma de pago (ver ventas.services.resumen_turno). No toca nada
    fiscal -eso es la factura global, ver facturacion:factura-global-."""
    turnos_qs = Turno.objects.select_related("punto_venta__almacen", "usuario")
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        turnos_qs = turnos_qs.filter(punto_venta__almacen__in=visibles)
    turno = get_object_or_404(turnos_qs, pk=pk)

    return render(
        request,
        "warehouses/turno_corte.html",
        {"turno": turno, "resumen": resumen_turno(turno), "active_module": "warehouses"},
    )


@permission_required("products.add_turno", raise_exception=True)
def abrir_turno_view(request):
    if request.method != "POST":
        return redirect("products:turno-list")

    punto_venta = get_object_or_404(PuntoVenta, pk=id_valido(request.POST.get("punto_venta")))
    visibles = almacenes_visibles(request.user)
    if visibles is not None and not visibles.filter(pk=punto_venta.almacen_id).exists():
        messages.error(request, "No puedes abrir un turno para una caja que no te corresponde.")
        return redirect("products:turno-list")
    if punto_venta.tipo not in tipos_punto_venta_de(request.user):
        messages.error(
            request,
            f'Tu rol no permite abrir turno en un punto de venta de tipo "{punto_venta.get_tipo_display()}".',
        )
        return redirect("products:turno-list")

    try:
        turno = abrir_turno(punto_venta=punto_venta, usuario=request.user)
    except ValidationError as e:
        for mensaje in e.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, f"Turno {turno.folio} abierto en {punto_venta.nombre} ({punto_venta.almacen.nombre}).")
    return redirect("products:turno-list")


@permission_required("products.change_turno", raise_exception=True)
def cerrar_turno_view(request, pk):
    if request.method != "POST":
        return redirect("products:turno-list")

    turno = get_object_or_404(Turno, pk=pk)
    visibles = almacenes_visibles(request.user)
    if visibles is not None and not visibles.filter(pk=turno.punto_venta.almacen_id).exists():
        messages.error(request, "No puedes cerrar un turno de una caja que no te corresponde.")
        return redirect("products:turno-list")
    if turno.punto_venta.tipo not in tipos_punto_venta_de(request.user):
        messages.error(request, "Tu rol no permite cerrar turnos de este tipo de punto de venta.")
        return redirect("products:turno-list")

    try:
        turno.cerrar()
    except ValidationError as e:
        for mensaje in e.messages:
            messages.error(request, mensaje)
        return redirect("products:turno-list")

    messages.success(request, f"Turno {turno.folio} cerrado.")
    # El cajero queda obligado a resolver aquí mismo el cierre fiscal del
    # día (ver facturacion:factura-global-generar): si quedaron ventas a
    # Público en general sin facturar, la siguiente pantalla es esa, no
    # el listado de turnos -puede salir sin generarla si de verdad hace
    # falta (ej. Facturama caído), y volver a intentarlo después desde
    # el turno ya cerrado-.
    if ventas_elegibles_para_global(turno).exists():
        return redirect("facturacion:factura-global-generar", turno_pk=turno.pk)
    return redirect("products:turno-list")
