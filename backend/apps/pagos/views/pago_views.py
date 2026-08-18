from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.pagos.forms import PagoForm
from apps.pagos.models import CuentaPorPagar


def registrar_pago_view(request, pk):
    cuenta = get_object_or_404(CuentaPorPagar, pk=pk)

    if cuenta.estatus in (CuentaPorPagar.Estatus.PAGADA, CuentaPorPagar.Estatus.CANCELADA):
        messages.info(request, "Esta cuenta por pagar ya no tiene saldo pendiente.")
        return redirect("pagos:cuenta-list")

    if request.method == "POST":
        form = PagoForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.cuenta_por_pagar = cuenta
            try:
                pago.full_clean()
            except ValidationError as e:
                for field, errores in e.message_dict.items():
                    for mensaje in errores:
                        form.add_error(None if field == "__all__" else field, mensaje)
            else:
                with transaction.atomic():
                    pago.save()
                    cuenta.actualizar_estatus()
                messages.success(request, "Pago registrado correctamente.")
                return redirect("pagos:cuenta-list")
    else:
        form = PagoForm(initial={"fecha_pago": timezone.localdate()})

    return render(
        request,
        "pagos/pago_form.html",
        {"cuenta": cuenta, "form": form, "active_module": "purchases"},
    )
