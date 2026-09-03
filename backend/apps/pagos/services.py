from datetime import timedelta
from decimal import Decimal
from email.mime.image import MIMEImage

from django.conf import settings
from django.contrib.staticfiles.finders import find as encontrar_estatico
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import CuentaPorPagar, Pago, ReciboPago

FIRMA_CORREO_PAGOS = (
    "Erick José Hernández Rocas · Depto. de Pagos · Celular: 933 148 0558 · "
    "Pagos@eltordillo.com.mx · Proveedores@eltordillo.com.mx"
)


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
def crear_recibo_pago(proveedor, fecha_pago, forma_pago, banco=None, numero_referencia="", observaciones=""):
    """Crea el encabezado (ReciboPago) de un evento de pago, con su número
    consecutivo propio. Se llama una sola vez por evento -sea un pago a una
    sola cuenta o varias juntas (ver registrar_pago_view /
    registrar_pago_multiple_view)- y cada Pago que se genere en ese evento
    debe apuntarle vía Pago.recibo."""
    recibo = ReciboPago(
        proveedor=proveedor,
        fecha_pago=fecha_pago,
        forma_pago=forma_pago,
        banco=banco,
        numero_referencia=numero_referencia,
        observaciones=observaciones,
    )
    # "numero" se asigna hasta save() (ver ReciboPago.save()); se excluye
    # aquí para no validar contra None.
    recibo.full_clean(exclude=["numero"])
    recibo.save()
    return recibo


def normalizar_whatsapp(telefono, respaldo=""):
    """Limpia un teléfono a solo dígitos y le antepone el código de país
    (52, México) si es un número local de 10 dígitos, para armar un link de
    WhatsApp (wa.me/<numero>). El contacto del proveedor
    (Proveedor.contacto_telefono) es texto libre sin garantía de formato,
    a diferencia de settings.WHATSAPP_NUMERO_PAGOS (`respaldo`), que ya se
    captura en formato internacional."""
    digitos = "".join(caracter for caracter in (telefono or "") if caracter.isdigit())
    if not digitos:
        return respaldo or ""
    if len(digitos) == 10:
        digitos = "52" + digitos
    return digitos


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


def calcular_datos_comprobante(pagos):
    """Reúne los datos comunes para el correo de notificación de pago a
    partir de uno o varios `Pago` (un pago combinado genera un Pago por
    cuenta, pero es un solo correo con todos los documentos). Asume que
    todos los pagos son del mismo proveedor, misma forma de pago/banco y
    misma fecha (es como se registran hoy los pagos combinados)."""
    documentos = [
        pago.cuenta_por_pagar.orden_compra.documento
        for pago in pagos
        if pago.cuenta_por_pagar.orden_compra.documento
    ]
    primero = pagos[0]
    return {
        "proveedor_nombre": primero.cuenta_por_pagar.proveedor.display_name,
        "documentos": ", ".join(documentos) if documentos else "sin folio capturado",
        "importe_total": f"${sum((p.monto_pagado for p in pagos), Decimal('0.00')):,.2f}",
        "banco": primero.banco.nombre if primero.banco_id else primero.forma_pago.descripcion,
        "fecha_pago": f"{primero.fecha_pago:%d/%m/%Y}",
    }


def enviar_comprobante_pago(pagos, destinatario, cc, adjuntos):
    """Envía la notificación de pago (uno o varios documentos a la vez) al
    correo indicado, con copia opcional, adjuntando los archivos subidos en
    el momento del envío (no se reutiliza ningún comprobante ya guardado).
    Propaga cualquier error de envío (SMTP sin configurar, credenciales
    inválidas, etc.) para que la vista lo muestre al usuario."""
    if not pagos:
        raise ValueError("No hay pagos para notificar.")
    if not adjuntos:
        raise ValueError("Adjunta al menos un documento.")

    datos = calcular_datos_comprobante(pagos)
    proveedor = pagos[0].cuenta_por_pagar.proveedor
    asunto = f"Comprobante de pago · {proveedor.display_name}"

    cuerpo_texto = (
        f"Documentos: {datos['documentos']}\n"
        f"Importe total pagado: {datos['importe_total']}\n"
        f"Banco de origen: {datos['banco']}\n"
        f"Fecha de pago: {datos['fecha_pago']}\n\n"
        "Adjunto a este correo encontrará el comprobante de pago correspondiente para su referencia y control.\n\n"
        "Le agradeceremos validar la recepción y correcta aplicación del pago a los documentos señalados.\n\n"
        "Este correo ha sido generado automáticamente como notificación de pago.\n\n"
        "Saludos cordiales,\n\n"
        f"{FIRMA_CORREO_PAGOS}"
    )

    logo_cid = "logo_tordillo"
    cuerpo_html = render_to_string("pagos/email/comprobante_pago.html", {**datos, "logo_cid": logo_cid})

    email = EmailMultiAlternatives(
        subject=asunto,
        body=cuerpo_texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
        cc=cc or None,
    )
    email.attach_alternative(cuerpo_html, "text/html")
    email.mixed_subtype = "related"

    logo_path = encontrar_estatico("src/logo.png")
    if logo_path:
        with open(logo_path, "rb") as f:
            logo = MIMEImage(f.read())
        logo.add_header("Content-ID", f"<{logo_cid}>")
        logo.add_header("Content-Disposition", "inline", filename="logo.png")
        email.attach(logo)

    for archivo in adjuntos:
        archivo.seek(0)
        email.attach(archivo.name, archivo.read(), archivo.content_type)

    email.send()
