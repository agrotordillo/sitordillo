from django.contrib import messages
from django.shortcuts import redirect, render

from apps.facturacion.forms import EmpresaForm
from apps.facturacion.models import Empresa


def empresa_config_view(request):
    empresa = Empresa.objects.first()

    if request.method == "POST":
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, "Datos de la empresa guardados correctamente.")
            return redirect("facturacion:empresa-config")
    else:
        form = EmpresaForm(instance=empresa)

    return render(
        request,
        "facturacion/empresa_form.html",
        {"form": form, "empresa": empresa, "active_module": "config"},
    )
