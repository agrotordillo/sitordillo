from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import errores_al_formulario
from apps.core.navegacion import url_de_regreso
from apps.core.parametros import ids_validos
from apps.pagos.forms import EnviarComprobanteForm, PagoEditForm, PagoForm, PagoMultipleForm
from apps.pagos.models import CuentaPorPagar, Pago
from apps.pagos.services import (
    bloquear_cuenta_por_pagar,
    bloquear_cuentas_por_pagar,
    calcular_datos_comprobante,
    construir_texto_whatsapp,
    construir_texto_whatsapp_pago,
    crear_recibo_pago,
    enviar_comprobante_pago,
    normalizar_whatsapp,
)

CUENTAS_PAGABLES = (CuentaPorPagar.Estatus.PENDIENTE, CuentaPorPagar.Estatus.PARCIAL)


@never_cache
@permission_required("pagos.add_pago", raise_exception=True)
def registrar_pago_view(request, pk):
    cuenta = get_object_or_404(CuentaPorPagar, pk=pk)
    sin_saldo = cuenta.estatus in (CuentaPorPagar.Estatus.PAGADA, CuentaPorPagar.Estatus.CANCELADA)

    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    if request.method == "POST" and sin_saldo:
        messages.info(request, "Esta cuenta por pagar ya no tiene saldo pendiente.")
        return redirect("pagos:cuenta-list")

    if request.method == "POST":
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            pago = form.save(commit=False)
            try:
                with transaction.atomic():
                    envio = reservar_envio(request)
                    # El saldo se valida con la cuenta bloqueada: dos pagos
                    # registrados a la vez no pueden rebasarlo (B16 en
                    # docs/AUDITORIA.md).
                    cuenta = bloquear_cuenta_por_pagar(cuenta.pk)
                    pago.cuenta_por_pagar = cuenta
                    pago.full_clean()
                    recibo = crear_recibo_pago(
                        proveedor=cuenta.proveedor,
                        fecha_pago=pago.fecha_pago,
                        forma_pago=pago.forma_pago,
                        banco=pago.banco,
                        numero_referencia=pago.numero_referencia,
                    )
                    pago.recibo = recibo
                    pago.save()
                    cuenta.actualizar_estatus()
                    envio.completar(reverse("pagos:cuenta-list"))
            except EnvioDuplicado as duplicado:
                return respuesta_envio_duplicado(request, duplicado.url_resultado, "pagos:cuenta-list")
            except ValidationError as e:
                errores_al_formulario(form, e)
            else:
                messages.success(request, f"Pago registrado correctamente (recibo {recibo.numero}).")
                return redirect("pagos:cuenta-list")
    else:
        form = PagoForm(initial={"fecha_pago": timezone.localdate()})

    pagos_con_preview = []
    for pago in cuenta.pagos.all():
        pago.pago_ids_modal = [pago.pk]
        pago.mensaje_whatsapp = construir_texto_whatsapp_pago(pago)
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
            "whatsapp_numero": normalizar_whatsapp(
                cuenta.proveedor.contacto_telefono, respaldo=settings.WHATSAPP_NUMERO_PAGOS
            ),
        },
    )


def _cuentas_seleccionadas_validas(request):
    """Recupera y valida las cuentas de un intento de pago múltiple: deben
    existir, seguir pagables y pertenecer todas al mismo proveedor. Devuelve
    (cuentas, error) donde `cuentas` viene ordenada por fecha_vencimiento
    (más antigua primero, orden por default del modelo) y `error` es un
    mensaje a mostrar si la selección ya no es válida."""
    enviados = request.POST.getlist("cuenta_ids")
    cuenta_ids = ids_validos(enviados)
    if len(cuenta_ids) < 2:
        return None, "Selecciona al menos dos cuentas para pagarlas juntas."

    cuentas = list(
        CuentaPorPagar.objects.filter(pk__in=cuenta_ids, estatus__in=CUENTAS_PAGABLES)
        .select_related("orden_compra", "orden_compra__proveedor")
    )
    if len(cuentas) != len(set(enviados)):
        return None, "Alguna de las cuentas seleccionadas ya no está disponible para pago."

    if len({c.orden_compra.proveedor_id for c in cuentas}) > 1:
        return None, "Solo puedes pagar juntas cuentas de un mismo proveedor."

    return cuentas, None


@permission_required("pagos.add_pago", raise_exception=True)
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


@permission_required("pagos.add_pago", raise_exception=True)
def registrar_pago_multiple_view(request):
    if request.method != "POST":
        return redirect("pagos:cuenta-list")

    # Antes de revisar las cuentas: si este envío ya se registró, sus cuentas
    # ya quedaron pagadas y la revisión lo rechazaría con un error confuso.
    if url := envio_ya_procesado(request):
        return respuesta_envio_duplicado(request, url)

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
        # "NaN" o "Infinity" son Decimal válidos, pero compararlos truena.
        if monto is None or not monto.is_finite() or monto < 0 or monto > cuenta.saldo_pendiente:
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
                envio = reservar_envio(request)
                # Saldos validados con las cuentas bloqueadas (ver
                # registrar_pago_view): el saldo que se revisó arriba pudo
                # cambiar mientras se capturaba.
                bloqueadas = bloquear_cuentas_por_pagar([c.pk for c in cuentas])
                # Un solo recibo (evento de pago) agrupa los pagos de todas
                # las cuentas seleccionadas -así se ven juntos después en
                # el listado de Pagos, en vez de como N registros sueltos-.
                recibo = crear_recibo_pago(
                    proveedor=cuentas[0].proveedor,
                    fecha_pago=form.cleaned_data["fecha_pago"],
                    forma_pago=form.cleaned_data["forma_pago"],
                    banco=form.cleaned_data.get("banco"),
                    numero_referencia=form.cleaned_data.get("numero_referencia", ""),
                    observaciones=form.cleaned_data.get("observaciones", ""),
                )
                pago_ids = []
                for cuenta in cuentas:
                    monto = montos[cuenta.pk]
                    if monto <= 0:
                        continue
                    cuenta = bloqueadas[cuenta.pk]
                    if comprobante:
                        comprobante.seek(0)
                    pago = Pago(
                        cuenta_por_pagar=cuenta,
                        recibo=recibo,
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
                url_confirmacion = f"{reverse('pagos:pago-multiple-confirmacion')}?ids={','.join(map(str, pago_ids))}"
                envio.completar(url_confirmacion)
        except EnvioDuplicado as duplicado:
            return respuesta_envio_duplicado(request, duplicado.url_resultado, "pagos:cuenta-list")
        except ValidationError as e:
            for mensaje in e.messages:
                form.add_error(None, mensaje)
        else:
            messages.success(request, f"Se registraron {len(pago_ids)} pagos correctamente (recibo {recibo.numero}).")
            return redirect(url_confirmacion)

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


@permission_required("pagos.view_pago", raise_exception=True)
def pago_multiple_confirmacion_view(request):
    pago_ids = ids_validos(request.GET.get("ids", ""))
    pagos = list(
        Pago.objects.filter(pk__in=pago_ids)
        .select_related("cuenta_por_pagar__orden_compra__proveedor", "banco", "forma_pago")
        .order_by("cuenta_por_pagar__fecha_vencimiento")
    )
    if not pagos:
        messages.error(request, "No se encontraron los pagos registrados.")
        return redirect("pagos:cuenta-list")

    proveedor = pagos[0].cuenta_por_pagar.proveedor
    return render(
        request,
        "pagos/pago_multiple_confirmacion.html",
        {
            "pagos": pagos,
            "pago_ids": [p.pk for p in pagos],
            "proveedor": proveedor,
            "total": sum((p.monto_pagado for p in pagos), Decimal("0.00")),
            "preview": calcular_datos_comprobante(pagos),
            "mensaje_whatsapp": construir_texto_whatsapp(pagos),
            "whatsapp_numero": normalizar_whatsapp(
                proveedor.contacto_telefono, respaldo=settings.WHATSAPP_NUMERO_PAGOS
            ),
            "active_module": "purchases",
        },
    )


@never_cache
@permission_required("pagos.change_pago", raise_exception=True)
def editar_pago_view(request, pk):
    """Corrige un pago ya registrado -monto, forma de pago, si cuenta como
    activo, etc.- para el caso de haberse equivocado al capturarlo (ver
    conversación de diseño: reemplaza al botón simple de Desactivar)."""
    pago = get_object_or_404(Pago, pk=pk)
    cuenta = pago.cuenta_por_pagar
    next_url = url_de_regreso(request, reverse("pagos:pago-registrar", args=[cuenta.pk]))

    if request.method == "POST":
        form = PagoEditForm(request.POST, request.FILES, instance=pago)
        if form.is_valid():
            pago = form.save(commit=False)
            try:
                with transaction.atomic():
                    # Mismo bloqueo que al registrar (B16 en docs/AUDITORIA.md):
                    # reactivar o subir el monto de un pago se valida contra
                    # el saldo con la cuenta bloqueada.
                    cuenta = bloquear_cuenta_por_pagar(cuenta.pk)
                    pago.cuenta_por_pagar = cuenta
                    pago.full_clean()
                    pago.save()
                    cuenta.actualizar_estatus()
            except ValidationError as e:
                errores_al_formulario(form, e)
            else:
                messages.success(request, f"Pago {pago.folio} actualizado correctamente.")
                return redirect(next_url)
    else:
        form = PagoEditForm(instance=pago)

    return render(
        request,
        "pagos/pago_editar_form.html",
        {"form": form, "pago": pago, "cuenta": cuenta, "next_url": next_url, "active_module": "purchases"},
    )


# Manda un correo desde la cuenta de la empresa con archivos que sube el
# usuario: exige poder registrar pagos, no solo verlos (B13 en
# docs/AUDITORIA.md).
@permission_required("pagos.add_pago", raise_exception=True)
def enviar_comprobante_view(request):
    if request.method != "POST":
        return redirect("pagos:cuenta-list")

    next_url = url_de_regreso(request, reverse("pagos:cuenta-list"))
    enviados = request.POST.getlist("pago_ids")
    pagos = list(
        Pago.objects.filter(pk__in=ids_validos(enviados)).select_related(
            "cuenta_por_pagar__orden_compra__proveedor", "banco", "forma_pago"
        )
    )
    if not pagos or len(pagos) != len(set(enviados)):
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
