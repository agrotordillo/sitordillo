from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Producto
from apps.products.forms import PaqueteComponenteFormSet


@permission_required("products.change_paquetecomponente", raise_exception=True)
def paquete_componentes_view(request, pk):
    paquete = get_object_or_404(Producto, pk=pk)
    if not paquete.es_paquete:
        raise Http404("Este producto no es un paquete/combo.")

    if request.method == "POST":
        formset = PaqueteComponenteFormSet(request.POST, instance=paquete, prefix="componentes")
        if formset.is_valid():
            with transaction.atomic():
                formset.save()
            messages.success(request, "Componentes del paquete actualizados correctamente.")
            return redirect("products:product-list")
    else:
        formset = PaqueteComponenteFormSet(instance=paquete, prefix="componentes")

    return render(
        request,
        "products/paquete_componentes_form.html",
        {"paquete": paquete, "formset": formset, "active_module": "products"},
    )
