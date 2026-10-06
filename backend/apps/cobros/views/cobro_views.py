from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.cobros.forms import CobroForm
from apps.cobros.models import CuentaPorCobrar
from apps.cobros.services import bloquear_cuenta_por_cobrar
from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import errores_al_formulario


@permission_required("cobros.add_cobro", raise_exception=True)
def registrar_cobro_view(request, pk):
    cuenta = get_object_or_404(CuentaPorCobrar, pk=pk)
    sin_saldo = cuenta.estatus in (CuentaPorCobrar.Estatus.COBRADA, CuentaPorCobrar.Estatus.CANCELADA)

    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    if request.method == "POST" and sin_saldo:
        messages.info(request, "Esta cuenta por cobrar ya no tiene saldo pendiente.")
        return redirect("cobros:cuenta-list")

    if request.method == "POST":
        form = CobroForm(request.POST, request.FILES)
        if form.is_valid():
            cobro = form.save(commit=False)
            try:
                with transaction.atomic():
                    envio = reservar_envio(request)
                    # El saldo se valida con la cuenta bloqueada: dos cobros
                    # registrados a la vez no pueden rebasarlo (B16 en
                    # docs/AUDITORIA.md).
                    cuenta = bloquear_cuenta_por_cobrar(cuenta.pk)
                    cobro.cuenta_por_cobrar = cuenta
                    cobro.full_clean()
                    cobro.save()
                    cuenta.actualizar_estatus()
                    envio.completar(reverse("cobros:cuenta-list"))
            except EnvioDuplicado as duplicado:
                return respuesta_envio_duplicado(request, duplicado.url_resultado, "cobros:cuenta-list")
            except ValidationError as e:
                errores_al_formulario(form, e)
            else:
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
