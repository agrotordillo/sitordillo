from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import ListView

from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.scoping import almacenes_visibles
from apps.inventario.forms import EnsamblePaqueteForm
from apps.inventario.models import EnsamblePaquete
from apps.inventario.services import registrar_ensamble_paquete


class EnsamblePaqueteListView(PermissionRequiredMixin, ListView):
    permission_required = "inventario.view_ensamblepaquete"
    model = EnsamblePaquete
    template_name = "inventario/ensamble_list.html"
    context_object_name = "ensambles"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        queryset = super().get_queryset().select_related("almacen", "paquete")
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            queryset = queryset.filter(almacen__in=visibles)
        return queryset


@permission_required("inventario.add_ensamblepaquete", raise_exception=True)
def crear_ensamble_view(request):
    if request.method == "POST":
        form = EnsamblePaqueteForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                ensamble = registrar_ensamble_paquete(
                    paquete=form.cleaned_data["paquete"],
                    almacen=form.cleaned_data["almacen"],
                    cantidad=form.cleaned_data["cantidad"],
                    fecha=form.cleaned_data["fecha"],
                    observaciones=form.cleaned_data["observaciones"],
                )
            except ERRORES_DE_NEGOCIO as e:
                for mensaje in mensajes_de_error(e):
                    form.add_error(None, mensaje)
            else:
                messages.success(
                    request,
                    f"Ensamble {ensamble.folio} registrado: {ensamble.cantidad} {ensamble.paquete.nombre} armados.",
                )
                return redirect("inventario:ensamble-list")
    else:
        form = EnsamblePaqueteForm(initial={"fecha": timezone.localdate()}, user=request.user)

    return render(
        request,
        "inventario/ensamble_form.html",
        {"form": form, "active_module": "warehouses"},
    )
