from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.pagos.forms import EnviarComprobanteForm, PagoForm, PagoMultipleForm
from apps.pagos.models import CuentaPorPagar, Pago
from apps.pagos.services import calcular_datos_comprobante, enviar_comprobante_pago

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

    pagos_con_preview = []
    for pago in cuenta.pagos.all():
        pago.pago_ids_modal = [pago.pk]
        pagos_con_preview.append((pago, calcular_datos_comprobante([pago])))

    return render(
        request,
        "pagos/pago_form.html",
        {
            "cuenta": cuenta,
            "form": form,
            "sin_saldo": sin_saldo,
            "pagos_con_preview": pagos_con_preview,
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
                pago_ids = []
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
                    pago_ids.append(pago.pk)
        except ValidationError as e:
            for errores in e.message_dict.values():
                for mensaje in errores:
                    form.add_error(None, mensaje)
        else:
            messages.success(request, f"Se registraron {len(pago_ids)} pagos correctamente.")
            ids_qs = ",".join(str(pk) for pk in pago_ids)
            return redirect(f"{reverse('pagos:pago-multiple-confirmacion')}?ids={ids_qs}")

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


def pago_multiple_confirmacion_view(request):
    ids_qs = request.GET.get("ids", "")
    pago_ids = [pk for pk in ids_qs.split(",") if pk]
    pagos = list(
        Pago.objects.filter(pk__in=pago_ids)
        .select_related("cuenta_por_pagar__orden_compra__proveedor", "banco", "forma_pago")
        .order_by("cuenta_por_pagar__fecha_vencimiento")
    )
    if not pagos:
        messages.error(request, "No se encontraron los pagos registrados.")
        return redirect("pagos:cuenta-list")

    return render(
        request,
        "pagos/pago_multiple_confirmacion.html",
        {
            "pagos": pagos,
            "pago_ids": [p.pk for p in pagos],
            "proveedor": pagos[0].cuenta_por_pagar.proveedor,
            "total": sum((p.monto_pagado for p in pagos), Decimal("0.00")),
            "preview": calcular_datos_comprobante(pagos),
            "active_module": "purchases",
        },
    )


def enviar_comprobante_view(request):
    if request.method != "POST":
        return redirect("pagos:cuenta-list")

    next_url = request.POST.get("next") or reverse("pagos:cuenta-list")
    pago_ids = request.POST.getlist("pago_ids")
    pagos = list(
        Pago.objects.filter(pk__in=pago_ids).select_related(
            "cuenta_por_pagar__orden_compra__proveedor", "banco", "forma_pago"
        )
    )
    if not pagos or len(pagos) != len(set(pago_ids)):
        messages.error(request, "No se encontraron los pagos a notificar.")
        return redirect(next_url)

    form = EnviarComprobanteForm(request.POST, request.FILES)
    if not form.is_valid():
        for errores in form.errors.values():
            for mensaje in errores:
                messages.error(request, mensaje)
        return redirect(next_url)

    try:
        enviar_comprobante_pago(
            pagos,
            destinatario=form.cleaned_data["destinatario"],
            cc=form.cleaned_data["cc"],
            adjuntos=form.cleaned_data["adjuntos"],
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:  # noqa: BLE001 - errores de SMTP/red, se muestran tal cual
        messages.error(request, f"No se pudo enviar el correo: {exc}")
    else:
        messages.success(request, f"Correo enviado a {form.cleaned_data['destinatario']}.")
    return redirect(next_url)
