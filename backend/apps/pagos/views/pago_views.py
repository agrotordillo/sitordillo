from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.pagos.forms import PagoForm, PagoMultipleForm
from apps.pagos.models import CuentaPorPagar, Pago
from apps.pagos.services import enviar_comprobante_email

CUENTAS_PAGABLES = (CuentaPorPagar.Estatus.PENDIENTE, CuentaPorPagar.Estatus.PARCIAL)


def registrar_pago_view(request, pk):
    cuenta = get_object_or_404(CuentaPorPagar, pk=pk)
    sin_saldo = cuenta.estatus in (CuentaPorPagar.Estatus.PAGADA, CuentaPorPagar.Estatus.CANCELADA)

    if request.method == "POST" and sin_saldo:
        messages.info(request, "Esta cuenta por pagar ya no tiene saldo pendiente.")
        return redirect("pagos:cuenta-list")

    if request.method == "POST":
        form = PagoForm(request.POST, request.FILES)
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
        {
            "cuenta": cuenta,
            "form": form,
            "sin_saldo": sin_saldo,
            "active_module": "purchases",
            "whatsapp_numero": settings.WHATSAPP_NUMERO_PAGOS,
        },
    )


def _cuentas_seleccionadas_validas(request):
    """Recupera y valida las cuentas de un intento de pago múltiple: deben
    existir, seguir pagables y pertenecer todas al mismo proveedor. Devuelve
    (cuentas, error) donde `cuentas` viene ordenada por fecha_vencimiento
    (más antigua primero, orden por default del modelo) y `error` es un
    mensaje a mostrar si la selección ya no es válida."""
    cuenta_ids = request.POST.getlist("cuenta_ids")
    if len(cuenta_ids) < 2:
        return None, "Selecciona al menos dos cuentas para pagarlas juntas."

    cuentas = list(
        CuentaPorPagar.objects.filter(pk__in=cuenta_ids, estatus__in=CUENTAS_PAGABLES)
        .select_related("orden_compra", "orden_compra__proveedor")
    )
    if len(cuentas) != len(set(cuenta_ids)):
        return None, "Alguna de las cuentas seleccionadas ya no está disponible para pago."

    if len({c.orden_compra.proveedor_id for c in cuentas}) > 1:
        return None, "Solo puedes pagar juntas cuentas de un mismo proveedor."

    return cuentas, None


def preparar_pago_multiple_view(request):
    if request.method != "POST":
        return redirect("pagos:cuenta-list")

    cuentas, error = _cuentas_seleccionadas_validas(request)
    if error:
        messages.error(request, error)
        return redirect("pagos:cuenta-list")

    form = PagoMultipleForm(initial={"fecha_pago": timezone.localdate()})
    return render(
        request,
        "pagos/pago_multiple_form.html",
        {
            "cuentas": cuentas,
            "form": form,
            "montos": None,
            "proveedor": cuentas[0].proveedor,
            "active_module": "purchases",
        },
    )


def registrar_pago_multiple_view(request):
    if request.method != "POST":
        return redirect("pagos:cuenta-list")

    cuentas, error = _cuentas_seleccionadas_validas(request)
    if error:
        messages.error(request, error)
        return redirect("pagos:cuenta-list")

    form = PagoMultipleForm(request.POST, request.FILES)

    montos = {}
    error_montos = None
    total = Decimal("0.00")
    for cuenta in cuentas:
        crudo = request.POST.get(f"monto_{cuenta.pk}", "").strip()
        try:
            monto = Decimal(crudo) if crudo else Decimal("0.00")
        except InvalidOperation:
            monto = None
        if monto is None or monto < 0 or monto > cuenta.saldo_pendiente:
            error_montos = "Revisa los montos capturados: no pueden ser negativos ni exceder el saldo pendiente de cada cuenta."
            monto = Decimal("0.00")
        montos[cuenta.pk] = monto
        total += monto

    if error_montos:
        form.add_error(None, error_montos)
    elif total <= 0:
        form.add_error(None, "Captura al menos un monto mayor a cero para alguna cuenta.")

    if form.is_valid() and not error_montos and total > 0:
        comprobante = form.cleaned_data.get("comprobante")
        try:
            with transaction.atomic():
                pagados = 0
                for cuenta in cuentas:
                    monto = montos[cuenta.pk]
                    if monto <= 0:
                        continue
                    if comprobante:
                        comprobante.seek(0)
                    pago = Pago(
                        cuenta_por_pagar=cuenta,
                        fecha_pago=form.cleaned_data["fecha_pago"],
                        monto_pagado=monto,
                        forma_pago=form.cleaned_data["forma_pago"],
                        banco=form.cleaned_data.get("banco"),
                        numero_referencia=form.cleaned_data.get("numero_referencia", ""),
                        comprobante=comprobante,
                        observaciones=form.cleaned_data.get("observaciones", ""),
                    )
                    pago.full_clean()
                    pago.save()
                    cuenta.actualizar_estatus()
                    pagados += 1
        except ValidationError as e:
            for errores in e.message_dict.values():
                for mensaje in errores:
                    form.add_error(None, mensaje)
        else:
            messages.success(request, f"Se registraron {pagados} pagos correctamente.")
            return redirect("pagos:cuenta-list")

    return render(
        request,
        "pagos/pago_multiple_form.html",
        {
            "cuentas": cuentas,
            "form": form,
            "montos": montos,
            "proveedor": cuentas[0].proveedor,
            "active_module": "purchases",
        },
    )


def enviar_comprobante_email_view(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    if request.method != "POST":
        return redirect("pagos:pago-registrar", pk=pago.cuenta_por_pagar_id)

    try:
        enviar_comprobante_email(pago)
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:  # noqa: BLE001 - errores de SMTP/red, se muestran tal cual
        messages.error(request, f"No se pudo enviar el correo: {exc}")
    else:
        messages.success(request, f"Comprobante enviado a {pago.cuenta_por_pagar.proveedor.contacto_email}.")
    return redirect("pagos:pago-registrar", pk=pago.cuenta_por_pagar_id)
