from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import CuentaPorPagar, Pago


def validar_limite_credito(proveedor, monto_nuevo, excluir_cuenta_id=None):
    """Devuelve un mensaje de error si `monto_nuevo` haría que el saldo
    pendiente del proveedor exceda su límite de crédito, o None si no hay
    problema (proveedores sin crédito autorizado no tienen límite que
    validar)."""
    if not proveedor.tiene_credito or proveedor.limite_credito <= 0:
        return None

    cuentas = CuentaPorPagar.objects.filter(
        orden_compra__proveedor=proveedor
    ).exclude(estatus=CuentaPorPagar.Estatus.CANCELADA)
    if excluir_cuenta_id:
        cuentas = cuentas.exclude(pk=excluir_cuenta_id)

    saldo_actual = sum((c.saldo_pendiente for c in cuentas), Decimal("0.00"))
    if saldo_actual + monto_nuevo > proveedor.limite_credito:
        disponible = proveedor.limite_credito - saldo_actual
        return (
            f"Esta cuenta excede el límite de crédito del proveedor. "
            f"Disponible: ${disponible} de ${proveedor.limite_credito}."
        )
    return None


@transaction.atomic
def generar_cuenta_por_pagar(orden_compra, fecha_emision=None, observaciones=""):
    if hasattr(orden_compra, "cuenta_por_pagar"):
        raise ValueError("Esta orden de compra ya tiene una cuenta por pagar generada.")

    proveedor = orden_compra.proveedor
    fecha_emision = fecha_emision or timezone.localdate()
    fecha_vencimiento = fecha_emision + timedelta(days=proveedor.dias_credito)
    fecha_limite_pronto_pago = None
    if proveedor.dias_pronto_pago:
        fecha_limite_pronto_pago = fecha_emision + timedelta(days=proveedor.dias_pronto_pago)

    monto_total = orden_compra.total.quantize(Decimal("0.01"))

    error_credito = validar_limite_credito(proveedor, monto_total)
    if error_credito:
        raise ValueError(error_credito)

    cuenta = CuentaPorPagar(
        orden_compra=orden_compra,
        monto_total=monto_total,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        fecha_limite_pronto_pago=fecha_limite_pronto_pago,
        observaciones=observaciones,
    )
    cuenta.full_clean()
    cuenta.save()
    return cuenta


@transaction.atomic
def registrar_pago(cuenta, fecha_pago, monto_pagado, forma_pago, aplica_descuento_pronto_pago=False, observaciones=""):
    pago = Pago(
        cuenta_por_pagar=cuenta,
        fecha_pago=fecha_pago,
        monto_pagado=monto_pagado,
        forma_pago=forma_pago,
        aplica_descuento_pronto_pago=aplica_descuento_pronto_pago,
        observaciones=observaciones,
    )
    pago.full_clean()
    pago.save()
    cuenta.actualizar_estatus()
    return pago


def enviar_comprobante_email(pago):
    """Envía el comprobante de un pago por correo al contacto del proveedor.
    Requiere que el pago tenga un archivo adjunto y que el proveedor tenga
    correo de contacto registrado; propaga cualquier error de envío (SMTP
    sin configurar, credenciales inválidas, etc.) para que la vista lo
    muestre al usuario."""
    if not pago.comprobante:
        raise ValueError("Este pago no tiene comprobante adjunto.")

    proveedor = pago.cuenta_por_pagar.proveedor
    if not proveedor.contacto_email:
        raise ValueError("Este proveedor no tiene correo de contacto registrado.")

    cuenta = pago.cuenta_por_pagar
    asunto = f"Comprobante de pago {pago.folio} · {proveedor.display_name}"
    cuerpo = (
        f"Se registró un pago de ${pago.monto_pagado} el {pago.fecha_pago:%d/%m/%Y}, "
        f"correspondiente a la cuenta {cuenta.folio} (orden de compra {cuenta.orden_compra.folio}).\n\n"
        "Se adjunta el comprobante correspondiente."
    )
    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[proveedor.contacto_email],
    )
    email.attach_file(pago.comprobante.path)
    email.send()
