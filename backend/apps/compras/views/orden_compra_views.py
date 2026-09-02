from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from apps.compras.models import OrdenCompra
from apps.compras.forms import CargarCFDIForm, OrdenCompraForm, OrdenCompraDetalleFormSet
from apps.compras.services import CFDIImportError, importar_cfdi_compra


class OrdenCompraListView(PermissionRequiredMixin, ListView):
    permission_required = "compras.view_ordencompra"
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


class OrdenCompraCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "compras.add_ordencompra"
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


@permission_required("compras.add_ordencompra", raise_exception=True)
def cargar_cfdi_view(request):
    if request.method == "POST":
        form = CargarCFDIForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                orden, no_encontrados = importar_cfdi_compra(form.cleaned_data["archivo"])
            except CFDIImportError as exc:
                form.add_error(None, str(exc))
            except ValidationError as exc:
                mensajes = exc.messages if hasattr(exc, "messages") else [str(exc)]
                for mensaje in mensajes:
                    form.add_error(None, mensaje)
            else:
                if no_encontrados:
                    detalle = ", ".join(
                        (c["codigo"] or c["descripcion"] or "?") for c in no_encontrados
                    )
                    messages.warning(
                        request,
                        f"Se creó la orden {orden.folio} desde el CFDI, pero "
                        f"{len(no_encontrados)} producto(s) no se encontraron y no se agregaron: "
                        f"{detalle}. Agrégalos manualmente y revisa el resto antes de guardar.",
                    )
                else:
                    messages.success(
                        request,
                        f"Orden {orden.folio} creada desde el CFDI. Revisa los datos antes de guardarla.",
                    )
                return redirect("compras:orden-update", pk=orden.pk)
    else:
        form = CargarCFDIForm()

    return render(
        request,
        "compras/cargar_cfdi_form.html",
        {"form": form, "active_module": "purchases"},
    )


class OrdenCompraUpdateView(PermissionRequiredMixin, UpdateView):
    # Ojo: "change_ordencompra" solo lo tiene "Compras - Completo", no
    # "Compras - Captura" (residente) - ver la nota en
    # accounts/migrations/0003_grupos_de_capacidades.py sobre por qué esta
    # misma vista maneja tanto editar un borrador como avanzar el estatus.
    permission_required = "compras.change_ordencompra"
    model = OrdenCompra
    form_class = OrdenCompraForm
    template_name = "compras/orden_compra_form.html"
    success_url = reverse_lazy("compras:orden-list")
    success_message = "Orden de compra actualizada correctamente."
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
