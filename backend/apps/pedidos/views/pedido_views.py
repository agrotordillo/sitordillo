from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.core.envio_unico import EnvioDuplicado, EnvioUnicoMixin, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.filtros_fecha import FiltroFechaMixin
from apps.core.scoping import almacenes_visibles
from apps.pedidos.forms import CancelarPedidoForm, PedidoDetalleFormSet, PedidoForm
from apps.pedidos.models import Pedido, PedidoDetalle
from apps.pedidos.services import (
    StockInsuficiente,
    apartar_inventario,
    bloquear_pedido_abierto,
    cancelar_pedido,
    liberar_inventario,
)
from apps.products.services import fijar_precios_autorizados, turno_abierto_de


def _pedidos_visibles(user):
    queryset = Pedido.objects.all()
    visibles = almacenes_visibles(user)
    if visibles is not None:
        queryset = queryset.filter(almacen__in=visibles)
    return queryset


class PedidoListView(FiltroFechaMixin, PermissionRequiredMixin, ListView):
    permission_required = "pedidos.view_pedido"
    model = Pedido
    template_name = "pedidos/pedido_list.html"
    context_object_name = "pedidos"
    extra_context = {"active_module": "orders"}
    filtro_fecha_campo = "fecha_pedido"

    def get_queryset(self):
        queryset = (
            _pedidos_visibles(self.request.user)
            .select_related("cliente", "almacen", "venta")
            .prefetch_related("detalles")
        )
        queryset = self.aplicar_filtro_fecha(queryset)
        estatus = self.request.GET.get("estatus", Pedido.Estatus.ABIERTO)
        if estatus in Pedido.Estatus.values:
            queryset = queryset.filter(estatus=estatus)
        return queryset

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["estatus_actual"] = self.request.GET.get("estatus", Pedido.Estatus.ABIERTO)
        data["estatus_opciones"] = Pedido.Estatus.choices
        return data


class PedidoFormsetMixin(EnvioUnicoMixin):
    """Guarda cabecera + líneas y aparta el inventario en una sola
    transacción: si algo no alcanza, no queda ni el pedido, ni el folio
    consumido, ni nada apartado. Al editar, primero se libera lo que el
    pedido ya tenía apartado -antes de guardar el formset, porque borrar
    una línea borraría en cascada su registro de apartado sin regresar la
    mercancía- y luego se vuelve a apartar con las líneas nuevas."""

    success_url = reverse_lazy("pedidos:pedido-list")
    error_message = "No fue posible guardar el pedido. Revisa los campos."

    def get_formset(self):
        if self.request.method == "POST":
            return PedidoDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
        return PedidoDetalleFormSet(instance=self.object, prefix="detalles")

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            data["formset"] = self.get_formset()
        return data

    def form_valid(self, form):
        formset = PedidoDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        fijar_precios_autorizados(
            formset, form.cleaned_data.get("cliente"), form.instance.almacen, PedidoDetalle.Estrategia.FIFO,
        )

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto al pedido.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        es_nuevo = form.instance.pk is None
        try:
            with transaction.atomic():
                envio = reservar_envio(self.request)
                if not es_nuevo:
                    pedido = bloquear_pedido_abierto(form.instance)
                    liberar_inventario(pedido, motivo=f"Edición de pedido {pedido.numero_documento}")
                self.object = form.save()
                formset.instance = self.object
                formset.save()
                apartar_inventario(self.object)
                envio.completar(self.get_success_url())
        except EnvioDuplicado as duplicado:
            return respuesta_envio_duplicado(self.request, duplicado.url_resultado, self.success_url)
        except ERRORES_DE_NEGOCIO as e:
            # La transacción ya se revirtió: un pedido nuevo no llegó a
            # existir (aunque form.save() le haya asignado pk en memoria),
            # así que la pantalla debe seguir siendo la de "registrar".
            if es_nuevo:
                self.object = None
            errores = e.errores if isinstance(e, StockInsuficiente) else mensajes_de_error(e)
            for error in errores:
                form.add_error(None, error)
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        messages.success(self.request, self.get_success_message())
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)


class PedidoCreateView(PermissionRequiredMixin, PedidoFormsetMixin, CreateView):
    permission_required = "pedidos.add_pedido"
    model = Pedido
    form_class = PedidoForm
    template_name = "pedidos/pedido_form.html"
    extra_context = {"active_module": "orders"}

    def dispatch(self, request, *args, **kwargs):
        # Igual que en Cotización: sucursal y punto de venta (y con él el
        # folio) se toman del turno propio y abierto de quien levanta el
        # pedido; sin uno abierto no hay de dónde sacarlos.
        if not self.has_permission():
            return self.handle_no_permission()
        self.turno = turno_abierto_de(request.user)
        if self.turno is None:
            messages.error(request, "No tienes un turno abierto. Ábrelo antes de levantar un pedido.")
            return redirect("products:turno-list")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.instance.almacen = self.turno.punto_venta.almacen
        form.instance.punto_venta = self.turno.punto_venta
        form.instance.turno = self.turno
        return form

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["turno"] = self.turno
        data["almacen"] = self.turno.punto_venta.almacen
        return data

    def get_success_message(self):
        return f"Pedido {self.object.numero_documento} registrado; su mercancía quedó apartada."


class PedidoUpdateView(PermissionRequiredMixin, PedidoFormsetMixin, UpdateView):
    permission_required = "pedidos.change_pedido"
    model = Pedido
    form_class = PedidoForm
    template_name = "pedidos/pedido_form.html"
    extra_context = {"active_module": "orders"}

    def get_queryset(self):
        return _pedidos_visibles(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission():
            return self.handle_no_permission()
        self.object = self.get_object()
        if self.object.estatus != Pedido.Estatus.ABIERTO:
            messages.error(request, "Solo se puede editar un pedido abierto.")
            return HttpResponseRedirect(reverse_lazy("pedidos:pedido-list"))
        return super().dispatch(request, *args, **kwargs)

    def get_success_message(self):
        return f"Pedido {self.object.numero_documento} actualizado."


@permission_required("pedidos.cancelar_pedido", raise_exception=True)
def cancelar_pedido_view(request, pk):
    pedido = get_object_or_404(_pedidos_visibles(request.user).select_related("cliente", "almacen"), pk=pk)
    if pedido.estatus != Pedido.Estatus.ABIERTO:
        messages.error(request, "Solo se puede cancelar un pedido abierto.")
        return redirect("pedidos:pedido-list")

    form = CancelarPedidoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancelar_pedido(pedido, motivo=form.cleaned_data["motivo"])
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(request, mensaje)
        else:
            messages.success(
                request,
                f"Pedido {pedido.numero_documento} cancelado; su mercancía regresó al inventario.",
            )
        return redirect("pedidos:pedido-list")

    return render(
        request,
        "pedidos/pedido_cancelar.html",
        {
            "pedido": pedido,
            "detalles": pedido.detalles.select_related("producto"),
            "form": form,
            "active_module": "orders",
        },
    )
