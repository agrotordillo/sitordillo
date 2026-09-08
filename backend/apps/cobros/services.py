from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CuentaPorCobrar, Cobro


def validar_limite_credito_cliente(cliente, monto_nuevo, excluir_cuenta_id=None):
    """Devuelve un mensaje de error si `monto_nuevo` haría que el saldo
    pendiente del cliente exceda su límite de crédito, o None si cabe.
    Asume que ya se validó aparte que el cliente tiene crédito autorizado
    (ver ventas.services.validar_venta_a_credito) -aquí solo se checa el
    número."""
    if cliente.limite_credito <= 0:
        return f'"{cliente.display_name}" tiene crédito autorizado pero sin límite asignado; no se puede vender a crédito.'

    cuentas = CuentaPorCobrar.objects.filter(
        venta__cliente=cliente
    ).exclude(estatus=CuentaPorCobrar.Estatus.CANCELADA)
    if excluir_cuenta_id:
        cuentas = cuentas.exclude(pk=excluir_cuenta_id)

    saldo_actual = sum((c.saldo_pendiente for c in cuentas), Decimal("0.00"))
    if saldo_actual + monto_nuevo > cliente.limite_credito:
        disponible = cliente.limite_credito - saldo_actual
        return (
            f'Esta venta excede el límite de crédito de "{cliente.display_name}". '
            f"Disponible: ${disponible} de ${cliente.limite_credito}."
        )
    return None


@transaction.atomic
def generar_cuenta_por_cobrar(venta, fecha_emision=None):
    """Genera la cuenta por cobrar de una venta a crédito. A diferencia de
    generar_cuenta_por_pagar (botón manual en Compras), esta se llama
    siempre automáticamente desde el flujo de registrar la venta -ver
    ventas.views.venta_views.VentaCreateView y
    cotizaciones.views.conversion_views.convertir_cotizacion_view-, nunca
    a mano, porque el total de una venta ya es definitivo desde que se
    registra (a diferencia de una compra, que puede recibirse parcial)."""
    if hasattr(venta, "cuenta_por_cobrar"):
        raise ValueError("Esta venta ya tiene una cuenta por cobrar generada.")

    cliente = venta.cliente
    fecha_emision = fecha_emision or timezone.localdate()
    fecha_vencimiento = fecha_emision + timedelta(days=cliente.dias_credito)
    monto_total = venta.total.quantize(Decimal("0.01"))

    cuenta = CuentaPorCobrar(
        venta=venta,
        monto_total=monto_total,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
    )
    cuenta.full_clean()
    cuenta.save()
    return cuenta


@transaction.atomic
def registrar_cobro(cuenta, fecha_cobro, monto_cobrado, forma_pago, banco=None, numero_referencia="", comprobante=None, observaciones=""):
    cobro = Cobro(
        cuenta_por_cobrar=cuenta,
        fecha_cobro=fecha_cobro,
        monto_cobrado=monto_cobrado,
        forma_pago=forma_pago,
        banco=banco,
        numero_referencia=numero_referencia,
        comprobante=comprobante,
        observaciones=observaciones,
    )
    cobro.full_clean()
    cobro.save()
    cuenta.actualizar_estatus()
    return cobro
