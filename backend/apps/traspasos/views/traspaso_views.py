from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from apps.core.scoping import almacenes_visibles
from apps.traspasos.models import Traspaso
from apps.traspasos.forms import TraspasoForm, TraspasoDetalleFormSet
from apps.traspasos.services import enviar_traspaso, recibir_traspaso


def _traspasos_visibles(user):
    queryset = Traspaso.objects.all()
    visibles = almacenes_visibles(user)
    if visibles is not None:
        # Un traspaso involucra dos almacenes; basta con que uno de los
        # dos sea suyo (lo está enviando o lo está recibiendo).
        queryset = queryset.filter(Q(almacen_origen__in=visibles) | Q(almacen_destino__in=visibles))
    return queryset


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
    traspaso = get_object_or_404(_traspasos_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("traspasos:traspaso-list")
    try:
        enviar_traspaso(traspaso)
        messages.success(request, f"Traspaso {traspaso.folio} enviado. Stock descontado del CEDIS.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("traspasos:traspaso-list")


@permission_required("traspasos.change_traspaso", raise_exception=True)
def traspaso_recibir_view(request, pk):
    traspaso = get_object_or_404(_traspasos_visibles(request.user), pk=pk)
    if request.method != "POST":
        return redirect("traspasos:traspaso-list")
    try:
        recibir_traspaso(traspaso)
        messages.success(request, f"Traspaso {traspaso.folio} recibido. Inventario dado de alta en la sucursal.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("traspasos:traspaso-list")
