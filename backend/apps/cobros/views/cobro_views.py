from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.cobros.forms import CobroForm
from apps.cobros.models import CuentaPorCobrar


@permission_required("cobros.add_cobro", raise_exception=True)
def registrar_cobro_view(request, pk):
    cuenta = get_object_or_404(CuentaPorCobrar, pk=pk)
    sin_saldo = cuenta.estatus in (CuentaPorCobrar.Estatus.COBRADA, CuentaPorCobrar.Estatus.CANCELADA)

    if request.method == "POST" and sin_saldo:
        messages.info(request, "Esta cuenta por cobrar ya no tiene saldo pendiente.")
        return redirect("cobros:cuenta-list")

    if request.method == "POST":
        form = CobroForm(request.POST, request.FILES)
        if form.is_valid():
            cobro = form.save(commit=False)
            cobro.cuenta_por_cobrar = cuenta
            try:
                cobro.full_clean()
            except ValidationError as e:
                for field, errores in e.message_dict.items():
                    for mensaje in errores:
                        form.add_error(None if field == "__all__" else field, mensaje)
            else:
                with transaction.atomic():
                    cobro.save()
                    cuenta.actualizar_estatus()
                messages.success(request, "Cobro registrado correctamente.")
                return redirect("cobros:cuenta-list")
    else:
        form = CobroForm(initial={"fecha_cobro": timezone.localdate()})

    return render(
        request,
        "cobros/cobro_form.html",
        {
            "cuenta": cuenta,
            "form": form,
            "sin_saldo": sin_saldo,
            "cobros": cuenta.cobros.all(),
            "active_module": "sales",
        },
    )
