from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.parametros import fecha, id_valido
from apps.core.scoping import almacenes_visibles
from apps.inventario.forms import MovimientoAlmacenDetalleFormSet, MovimientoAlmacenForm, conceptos_agrupados
from apps.inventario.models import MovimientoAlmacen, MovimientoAlmacenDetalle, MovimientoAlmacenLote
from apps.inventario.services import (
    aplicar_movimiento_almacen,
    cancelar_movimiento_almacen,
    validar_stock_movimiento_almacen,
)
from apps.products.models import Almacen

# Mismo filtro de fecha que la pantalla del sistema anterior: un operador
# y una fecha (dos con "Entre").
OPERADORES_FECHA = [
    ("igual", "Exactamente igual"),
    ("desde", "Mayor o igual a"),
    ("hasta", "Menor o igual a"),
    ("entre", "Entre"),
]


def _movimientos_visibles(user):
    queryset = MovimientoAlmacen.objects.all()
    visibles = almacenes_visibles(user)
    if visibles is not None:
        # La devolución en móvil involucra dos almacenes: basta con que uno
        # de los dos sea suyo, igual que un traspaso.
        queryset = queryset.filter(Q(almacen__in=visibles) | Q(almacen_destino__in=visibles))
    return queryset


class MovimientoAlmacenListView(PermissionRequiredMixin, ListView):
    """Solo movimientos manuales: ventas, traspasos, compras y conversiones
    se ven en su propio módulo, en Kardex y en Movimientos con costo."""

    permission_required = "inventario.view_movimientoalmacen"
    model = MovimientoAlmacen
    template_name = "inventario/movimiento_almacen_list.html"
    context_object_name = "movimientos"
    extra_context = {"active_module": "warehouses"}
    paginate_by = 50

    def _filtros(self):
        get = self.request.GET
        operador = get.get("fecha_op", "igual")
        if operador not in dict(OPERADORES_FECHA):
            operador = "igual"
        return {
            "fecha_op": operador,
            "fecha": get.get("fecha", "").strip(),
            "fecha_fin": get.get("fecha_fin", "").strip(),
            "estado": get.get("estado", "").strip(),
            "almacen": get.get("almacen", "").strip(),
            "concepto": get.get("concepto", "").strip(),
        }

    def get_queryset(self):
        filtros = self._filtros()
        qs = _movimientos_visibles(self.request.user).select_related("almacen", "almacen_destino", "proveedor")

        dia = fecha(filtros["fecha"])
        if dia:
            operador = filtros["fecha_op"]
            if operador == "igual":
                qs = qs.filter(fecha=dia)
            elif operador == "desde":
                qs = qs.filter(fecha__gte=dia)
            elif operador == "hasta":
                qs = qs.filter(fecha__lte=dia)
            else:
                qs = qs.filter(fecha__gte=dia)
                fecha_fin = fecha(filtros["fecha_fin"])
                if fecha_fin:
                    qs = qs.filter(fecha__lte=fecha_fin)

        if filtros["estado"]:
            qs = qs.filter(estado=filtros["estado"])
        if filtros["almacen"]:
            almacen_id = id_valido(filtros["almacen"])
            qs = qs.filter(Q(almacen_id=almacen_id) | Q(almacen_destino_id=almacen_id)) if almacen_id else qs.none()
        if filtros["concepto"]:
            qs = qs.filter(concepto=filtros["concepto"])

        return qs.order_by("-fecha", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtros = self._filtros()
        context.update(filtros)
        context["querystring"] = urlencode({clave: valor for clave, valor in filtros.items() if valor})
        context["operadores_fecha"] = OPERADORES_FECHA
        context["estados"] = MovimientoAlmacen.Estado.choices
        context["conceptos"] = conceptos_agrupados()
        almacenes = Almacen.objects.filter(is_active=True)
        visibles = almacenes_visibles(self.request.user)
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        context["almacenes"] = almacenes
        return context


class MovimientoAlmacenDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "inventario.view_movimientoalmacen"
    model = MovimientoAlmacen
    template_name = "inventario/movimiento_almacen_detail.html"
    context_object_name = "movimiento"
    extra_context = {"active_module": "warehouses"}

    def get_queryset(self):
        lotes_qs = MovimientoAlmacenLote.objects.select_related("lote", "lote_destino")
        detalles_qs = MovimientoAlmacenDetalle.objects.select_related("producto").prefetch_related(
            Prefetch("lotes", queryset=lotes_qs)
        )
        return (
            _movimientos_visibles(self.request.user)
            .select_related(
                "almacen", "almacen_destino", "proveedor", "orden_compra", "movimiento_relacionado", "created_by"
            )
            .prefetch_related(Prefetch("detalles", queryset=detalles_qs), "movimientos_derivados")
        )


class _MovimientoAlmacenFormMixin:
    """Cabecera + productos, compartido por alta y edición (ambas solo en
    borrador: aquí no se toca inventario, eso lo hace Aplicar)."""

    model = MovimientoAlmacen
    form_class = MovimientoAlmacenForm
    template_name = "inventario/movimiento_almacen_form.html"
    extra_context = {"active_module": "warehouses"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Para mostrar u ocultar proveedor / almacén destino según el concepto.
        data["conceptos_con_proveedor"] = sorted(MovimientoAlmacen.CONCEPTOS_CON_PROVEEDOR)
        data["concepto_movil"] = MovimientoAlmacen.Concepto.SALIDA_DEVOLUCION_MOVIL
        if "formset" not in data:
            data["formset"] = MovimientoAlmacenDetalleFormSet(
                self.request.POST or None, instance=self.object, prefix="detalles"
            )
        return data

    def form_valid(self, form):
        formset = MovimientoAlmacenDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        lineas = [
            cd for f in formset
            if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
        ]
        if not lineas:
            form.add_error(None, "Agrega al menos un producto al movimiento.")
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        # Igual que en traspasos: una salida que de entrada ya no cabe en
        # el almacén se avisa aquí, no hasta que alguien intente aplicarla.
        if form.cleaned_data["concepto"] not in MovimientoAlmacen.CONCEPTOS_ENTRADA:
            errores = validar_stock_movimiento_almacen(
                form.cleaned_data["almacen"], [(cd["producto"], cd["cantidad"]) for cd in lineas]
            )
            if errores:
                for error in errores:
                    form.add_error(None, error)
                return self.render_to_response(self.get_context_data(form=form, formset=formset))

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, self.success_message.format(folio=self.object.folio))
        return HttpResponseRedirect(reverse("inventario:movimiento-almacen-detail", args=[self.object.pk]))

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar el movimiento. Revisa los campos.")
        return super().form_invalid(form)


class MovimientoAlmacenCreateView(PermissionRequiredMixin, _MovimientoAlmacenFormMixin, CreateView):
    permission_required = "inventario.add_movimientoalmacen"
    success_message = "Movimiento {folio} guardado en borrador. Revísalo y aplícalo para afectar existencias."


class MovimientoAlmacenUpdateView(PermissionRequiredMixin, _MovimientoAlmacenFormMixin, UpdateView):
    permission_required = "inventario.change_movimientoalmacen"
    success_message = "Movimiento {folio} actualizado."

    def get_queryset(self):
        return _movimientos_visibles(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return self.handle_no_permission()
        movimiento = self.get_object()
        if movimiento.estado != MovimientoAlmacen.Estado.BORRADOR:
            messages.error(request, "Solo se puede editar un movimiento en borrador.")
            return redirect("inventario:movimiento-almacen-detail", pk=movimiento.pk)
        return super().dispatch(request, *args, **kwargs)


@permission_required("inventario.change_movimientoalmacen", raise_exception=True)
def movimiento_almacen_aplicar_view(request, pk):
    movimiento = get_object_or_404(_movimientos_visibles(request.user), pk=pk)
    if request.method == "POST":
        try:
            aplicar_movimiento_almacen(movimiento)
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(request, mensaje)
        else:
            messages.success(request, f"Movimiento {movimiento.folio} aplicado: existencias actualizadas.")
    return redirect("inventario:movimiento-almacen-detail", pk=movimiento.pk)


@permission_required("inventario.change_movimientoalmacen", raise_exception=True)
def movimiento_almacen_cancelar_view(request, pk):
    movimiento = get_object_or_404(_movimientos_visibles(request.user), pk=pk)
    if request.method == "POST":
        try:
            cancelar_movimiento_almacen(movimiento, motivo=request.POST.get("motivo", "").strip()[:255])
        except ERRORES_DE_NEGOCIO as e:
            for mensaje in mensajes_de_error(e):
                messages.error(request, mensaje)
        else:
            messages.success(request, f"Movimiento {movimiento.folio} cancelado.")
    return redirect("inventario:movimiento-almacen-detail", pk=movimiento.pk)
