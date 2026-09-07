from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView

from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen, Turno
from apps.products.services import abrir_turno


class TurnoListView(PermissionRequiredMixin, ListView):
    """Apertura/cierre de turno por sucursal (ver Turno y su uso en
    Gasto.turno). Un usuario restringido solo ve y abre turnos de sus
    sucursales asignadas."""

    permission_required = "products.view_turno"
    model = Turno
    template_name = "warehouses/turno_list.html"
    context_object_name = "turnos"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset().select_related("almacen", "usuario")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        almacenes = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.SUCURSAL)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes
        return context


@permission_required("products.add_turno", raise_exception=True)
def abrir_turno_view(request):
    if request.method != "POST":
        return redirect("products:turno-list")

    almacen = get_object_or_404(Almacen, pk=request.POST.get("almacen"))
    visibles = almacenes_visibles(request.user)
    if visibles is not None and not visibles.filter(pk=almacen.pk).exists():
        messages.error(request, "No puedes abrir un turno para una sucursal que no te corresponde.")
        return redirect("products:turno-list")

    try:
        turno = abrir_turno(almacen=almacen, usuario=request.user)
    except ValidationError as e:
        for mensaje in e.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, f"Turno {turno.folio} abierto en {almacen.nombre}.")
    return redirect("products:turno-list")


@permission_required("products.change_turno", raise_exception=True)
def cerrar_turno_view(request, pk):
    if request.method != "POST":
        return redirect("products:turno-list")

    turno = get_object_or_404(Turno, pk=pk)
    visibles = almacenes_visibles(request.user)
    if visibles is not None and not visibles.filter(pk=turno.almacen_id).exists():
        messages.error(request, "No puedes cerrar un turno de una sucursal que no te corresponde.")
        return redirect("products:turno-list")

    try:
        turno.cerrar()
    except ValidationError as e:
        for mensaje in e.messages:
            messages.error(request, mensaje)
    else:
        messages.success(request, f"Turno {turno.folio} cerrado.")
    return redirect("products:turno-list")
