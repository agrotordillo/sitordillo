from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.core.scoping import almacenes_visibles
from apps.traspasos.models import Traspaso, TraspasoDetalle, TraspasoLote
from apps.traspasos.forms import TraspasoForm, TraspasoDetalleFormSet
from apps.traspasos.services import (
    cancelar_traspaso,
    enviar_traspaso,
    recibir_traspaso,
    validar_stock_disponible_traspaso,
)


def _traspasos_visibles(user):
    queryset = Traspaso.objects.all()
    visibles = almacenes_visibles(user)
    if visibles is not None:
        # Un traspaso involucra dos almacenes; basta con que uno de los
        # dos sea suyo (lo está enviando o lo está recibiendo).
        queryset = queryset.filter(Q(almacen_origen__in=visibles) | Q(almacen_destino__in=visibles))
    return queryset


def _pertenece_a_almacen(user, almacen_id):
    """True si el usuario no tiene restricción de sucursal (Administrador/
    Auxiliar), o si el almacén dado es una de las suyas."""
    visibles = almacenes_visibles(user)
    return visibles is None or visibles.filter(pk=almacen_id).exists()


class TraspasoListView(PermissionRequiredMixin, ListView):
    permission_required = "traspasos.view_traspaso"
    model = Traspaso
    template_name = "traspasos/traspaso_list.html"
    context_object_name = "traspasos"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        return (
            _traspasos_visibles(self.request.user)
            .select_related("almacen_origen", "almacen_destino")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Para mostrar Enviar/Recibir solo del lado que realmente le toca a
        # cada quien (el backend ya lo exige en las vistas; esto es solo
        # para no ofrecer un botón que va a rebotar con error).
        visibles = almacenes_visibles(self.request.user)
        context["almacenes_propios_ids"] = (
            None if visibles is None else set(visibles.values_list("pk", flat=True))
        )
        return context


class TraspasoDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "traspasos.view_traspaso"
    model = Traspaso
    template_name = "traspasos/traspaso_detail.html"
    context_object_name = "traspaso"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        lotes_qs = TraspasoLote.objects.select_related("lote_origen", "lote_destino")
        detalles_qs = TraspasoDetalle.objects.select_related("producto").prefetch_related(
            Prefetch("lotes", queryset=lotes_qs)
        )
        return (
            _traspasos_visibles(self.request.user)
            .select_related("almacen_origen", "almacen_destino", "created_by")
            .prefetch_related(Prefetch("detalles", queryset=detalles_qs))
        )


class TraspasoCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "traspasos.add_traspaso"
    model = Traspaso
    form_class = TraspasoForm
    template_name = "traspasos/traspaso_form.html"
    success_url = reverse_lazy("traspasos:traspaso-list")
    success_message = "Traspaso creado correctamente."
    extra_context = {"active_module": "warehouses"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = TraspasoDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = TraspasoDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = TraspasoDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto al traspaso.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        # No tiene sentido dejar guardar (ni en borrador) una cantidad que
        # de entrada ya no cabe en el almacén origen: quien lo crea debe
        # enterarse aquí, no hasta que alguien intente enviarlo.
        errores_stock = validar_stock_disponible_traspaso(
            form.cleaned_data["almacen_origen"],
            [(cd["producto"], cd["cantidad"], cd["estrategia_salida"]) for cd in lineas],
        )
        if errores_stock:
            for error in errores_stock:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el traspaso. Revisa los campos.")
        return super().form_invalid(form)


class TraspasoUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "traspasos.change_traspaso"
    model = Traspaso
    form_class = TraspasoForm
    template_name = "traspasos/traspaso_form.html"
    success_url = reverse_lazy("traspasos:traspaso-list")
    success_message = "Traspaso actualizado correctamente."
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        return _traspasos_visibles(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estatus != Traspaso.Estatus.BORRADOR:
            messages.error(
                request,
                "Solo se puede editar un traspaso en borrador; este ya fue enviado o cancelado.",
            )
            return HttpResponseRedirect(reverse_lazy("traspasos:traspaso-list"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = TraspasoDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = TraspasoDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = TraspasoDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto al traspaso.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        errores_stock = validar_stock_disponible_traspaso(
            form.cleaned_data["almacen_origen"],
            [(cd["producto"], cd["cantidad"], cd["estrategia_salida"]) for cd in lineas],
        )
        if errores_stock:
            for error in errores_stock:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el traspaso. Revisa los campos.")
        return super().form_invalid(form)


@permission_required("traspasos.change_traspaso", raise_exception=True)
def traspaso_enviar_view(request, pk):
    """Solo alguien del almacén de ORIGEN puede confirmar el envío -no
    basta con que el traspaso le sea "visible" por ser el destino (quien
    lo solicitó), porque eso permitiría auto-aprobarse el envío de
    mercancía de un almacén que no es el suyo sin que origen participe."""
    traspaso = get_object_or_404(_traspasos_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("traspasos:traspaso-list")

    if not _pertenece_a_almacen(request.user, traspaso.almacen_origen_id):
        messages.error(request, "Solo alguien del almacén de origen puede enviar este traspaso.")
        return redirect("traspasos:traspaso-list")

    lineas = [
        (d.producto, d.cantidad, d.estrategia_salida) for d in traspaso.detalles.select_related("producto")
    ]
    errores_stock = validar_stock_disponible_traspaso(traspaso.almacen_origen, lineas)
    if errores_stock:
        for error in errores_stock:
            messages.error(request, error)
        return redirect("traspasos:traspaso-list")

    try:
        enviar_traspaso(traspaso)
        messages.success(request, f"Traspaso {traspaso.folio} enviado. Stock descontado de {traspaso.almacen_origen.nombre}.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("traspasos:traspaso-list")


@permission_required("traspasos.change_traspaso", raise_exception=True)
def traspaso_recibir_view(request, pk):
    """Solo alguien del almacén DESTINO puede confirmar la recepción -no
    basta con que el traspaso le sea "visible" por ser el origen, porque
    eso permitiría darse de alta inventario en una sucursal ajena sin que
    esa sucursal confirme haberlo recibido físicamente."""
    traspaso = get_object_or_404(_traspasos_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("traspasos:traspaso-list")

    if not _pertenece_a_almacen(request.user, traspaso.almacen_destino_id):
        messages.error(request, "Solo alguien del almacén de destino puede recibir este traspaso.")
        return redirect("traspasos:traspaso-list")

    try:
        recibir_traspaso(traspaso)
        messages.success(request, f"Traspaso {traspaso.folio} recibido. Inventario dado de alta en la sucursal.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("traspasos:traspaso-list")


@permission_required("traspasos.change_traspaso", raise_exception=True)
def traspaso_cancelar_view(request, pk):
    """Cancela un traspaso en borrador (todavía sin mover inventario).
    Cualquiera de los dos lados (origen o destino) puede cancelarlo, igual
    que cualquiera de los dos puede crearlo."""
    traspaso = get_object_or_404(_traspasos_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("traspasos:traspaso-list")
    try:
        cancelar_traspaso(traspaso)
        messages.success(request, f"Traspaso {traspaso.folio} cancelado.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("traspasos:traspaso-list")
