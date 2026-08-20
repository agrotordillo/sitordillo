from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.db import transaction
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.compras.models import OrdenCompra
from apps.compras.forms import OrdenCompraForm, OrdenCompraDetalleFormSet

ESTATUS_EDITABLES = (OrdenCompra.Estatus.BORRADOR, OrdenCompra.Estatus.ENVIADA)


class OrdenCompraListView(ListView):
    model = OrdenCompra
    template_name = "compras/orden_compra_list.html"
    context_object_name = "ordenes"
    extra_context = {"active_module": "purchases"}
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related("proveedor").prefetch_related("detalles")
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(folio__icontains=q)
                | Q(proveedor__nombre_fiscal__icontains=q)
                | Q(proveedor__nombre_comercial__icontains=q)
                | Q(proveedor__rfc__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "").strip()
        return context


class OrdenCompraCreateView(CreateView):
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = "compras/orden_compra_form.html"
    success_url = reverse_lazy("compras:orden-list")
    success_message = "Orden de compra creada correctamente."
    extra_context = {"active_module": "purchases"}

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = OrdenCompraDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = OrdenCompraDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = OrdenCompraDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la orden de compra. Revisa los campos.")
        return super().form_invalid(form)


class OrdenCompraUpdateView(UpdateView):
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = "compras/orden_compra_form.html"
    success_url = reverse_lazy("compras:orden-list")
    success_message = "Orden de compra actualizada correctamente."
    extra_context = {"active_module": "purchases"}

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estatus not in ESTATUS_EDITABLES:
            messages.error(
                request,
                "Solo se puede editar una orden de compra en borrador o enviada, antes de recibir mercancía.",
            )
            return HttpResponseRedirect(reverse_lazy("compras:orden-list"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if "formset" not in data:
            if self.request.method == "POST":
                data["formset"] = OrdenCompraDetalleFormSet(self.request.POST, instance=self.object, prefix="detalles")
            else:
                data["formset"] = OrdenCompraDetalleFormSet(instance=self.object, prefix="detalles")
        return data

    def form_valid(self, form):
        formset = OrdenCompraDetalleFormSet(self.request.POST, instance=form.instance, prefix="detalles")
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, formset=formset))
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "No fue posible guardar la orden de compra. Revisa los campos.")
        return super().form_invalid(form)
