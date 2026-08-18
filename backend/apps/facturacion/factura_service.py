from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .facturama_client import FacturamaClient, FacturamaError
from .models import Empresa, Factura

TWO_PLACES = Decimal("0.01")


def _desglosar_linea(detalle):
    """Desglosa impuestos de una línea de venta asumiendo que
    `precio_unitario` ya incluye todos los impuestos (IVA e IEPS, si
    aplican) — así se etiquetan los precios al público en México. El IEPS
    se calcula sobre la base sin impuestos, y el IVA sobre (base + IEPS),
    que es la forma fiscalmente correcta cuando ambos aplican al mismo
    producto."""
    producto = detalle.producto
    cantidad = detalle.cantidad
    descuento_pct = detalle.descuento or Decimal("0")

    importe_bruto = (detalle.precio_unitario * cantidad).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    descuento_monto = (importe_bruto * descuento_pct / Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    importe_neto_con_impuestos = importe_bruto - descuento_monto

    tasa_iva = (producto.tasa_iva / Decimal("100")) if producto.tipo_iva == producto.TipoIVA.GRAVADO else Decimal("0")
    tasa_ieps = (producto.tasa_ieps / Decimal("100")) if producto.aplica_ieps and producto.tasa_ieps else Decimal("0")

    factor = (Decimal("1") + tasa_ieps) * (Decimal("1") + tasa_iva)
    base = (importe_neto_con_impuestos / factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    ieps_monto = (base * tasa_ieps).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    iva_monto = ((base + ieps_monto) * tasa_iva).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    precio_unitario_sin_impuestos = (base / cantidad) if cantidad else base

    return {
        "producto": producto,
        "cantidad": cantidad,
        "precio_unitario_sin_impuestos": precio_unitario_sin_impuestos,
        "base": base,
        "descuento_monto": descuento_monto,
        "tasa_iva": tasa_iva,
        "iva_monto": iva_monto,
        "tasa_ieps": tasa_ieps,
        "ieps_monto": ieps_monto,
    }


def construir_payload_cfdi(factura):
    venta = factura.venta
    cliente = venta.cliente

    items = []
    for detalle in venta.detalles.select_related("producto"):
        d = _desglosar_linea(detalle)
        producto = d["producto"]
        taxes = []
        if d["tasa_iva"] > 0:
            taxes.append({
                "Total": float(d["iva_monto"]),
                "Name": "IVA",
                "Base": float(d["base"] + d["ieps_monto"]),
                "Rate": float(d["tasa_iva"]),
                "IsRetention": False,
            })
        if d["tasa_ieps"] > 0:
            taxes.append({
                "Total": float(d["ieps_monto"]),
                "Name": "IEPS",
                "Base": float(d["base"]),
                "Rate": float(d["tasa_ieps"]),
                "IsRetention": False,
            })

        total_impuestos = d["iva_monto"] + d["ieps_monto"]
        total_linea = d["base"] - d["descuento_monto"] + total_impuestos

        items.append({
            "ProductCode": producto.clave_prod_serv_sat.clave,
            "IdentificationNumber": producto.sku,
            "Description": producto.nombre,
            # Facturama exige longitud 1-20 y no acepta '|'; el nombre oficial
            # del SAT puede ser más largo, así que se trunca defensivamente.
            "Unit": producto.clave_unidad_sat.nombre.replace("|", "")[:20],
            "UnitCode": producto.clave_unidad_sat.clave,
            "UnitPrice": float(d["precio_unitario_sin_impuestos"]),
            "Quantity": float(d["cantidad"]),
            "Subtotal": float(d["base"]),
            "Discount": float(d["descuento_monto"]),
            "Total": float(total_linea),
            "TaxObject": "02" if taxes else "01",
            "Taxes": taxes,
        })

    return {
        # Serie/Folio no se envían: Facturama los asigna según la serie
        # configurada en el perfil fiscal de la cuenta (ver
        # https://apisandbox.facturama.mx/guias/perfil-fiscal). Nuestro
        # folio interno (Factura.numero_folio) es solo para referencia
        # antes de timbrar; se sincroniza con lo que Facturama devuelva.
        "Currency": factura.moneda,
        "ExpeditionPlace": factura.lugar_expedicion,
        "CfdiType": "I",
        "PaymentForm": venta.forma_pago.clave,
        "PaymentMethod": factura.metodo_pago.clave,
        "Exportation": "01",
        "Receiver": {
            "Rfc": cliente.rfc,
            "Name": cliente.nombre_fiscal,
            "CfdiUse": factura.uso_cfdi.clave,
            "FiscalRegime": cliente.regimen_fiscal.clave,
            "TaxZipCode": cliente.codigo_postal,
        },
        "Items": items,
    }


@transaction.atomic
def generar_factura(venta, uso_cfdi, metodo_pago, serie=None, observaciones=""):
    if hasattr(venta, "factura"):
        raise ValueError("Esta venta ya tiene una factura generada.")

    empresa = Empresa.objects.first()
    if not empresa:
        raise ValueError("Registra primero los datos fiscales de la empresa.")

    serie = serie or empresa.serie_default
    numero_folio = empresa.tomar_siguiente_folio()

    factura = Factura(
        venta=venta,
        serie=serie,
        numero_folio=numero_folio,
        uso_cfdi=uso_cfdi,
        metodo_pago=metodo_pago,
        lugar_expedicion=empresa.codigo_postal,
        observaciones=observaciones,
    )
    try:
        factura.full_clean()
    except ValidationError:
        empresa.siguiente_folio -= 1
        empresa.save(update_fields=["siguiente_folio", "updated_at", "updated_by"])
        raise
    factura.save()
    return factura


def timbrar_factura(factura):
    payload = construir_payload_cfdi(factura)
    client = FacturamaClient()
    try:
        data = client.crear_cfdi(payload)
    except FacturamaError as e:
        factura.estatus = Factura.Estatus.ERROR
        factura.mensaje_error = str(e)
        factura.save(update_fields=["estatus", "mensaje_error", "updated_at", "updated_by"])
        raise

    factura.facturama_id = data.get("Id", "")
    complemento = data.get("Complement") or {}
    timbre = complemento.get("TaxStamp") or {}
    factura.uuid_fiscal = timbre.get("Uuid") or data.get("Uuid") or ""
    # Serie/Folio reales los asigna Facturama; se sincronizan si vienen en
    # la respuesta (el nombre exacto del campo se confirma en producción).
    if data.get("Serie"):
        factura.serie = data["Serie"]
    if data.get("Folio"):
        factura.numero_folio = int(data["Folio"])
    factura.estatus = Factura.Estatus.TIMBRADA
    factura.fecha_timbrado = timezone.now()
    factura.mensaje_error = ""
    factura.save()
    return factura, data


def cancelar_factura(factura, motivo="02", uuid_reemplazo=None):
    client = FacturamaClient()
    client.cancelar_cfdi(factura.facturama_id, motivo=motivo, uuid_reemplazo=uuid_reemplazo)
    factura.estatus = Factura.Estatus.CANCELADA
    factura.save(update_fields=["estatus", "updated_at", "updated_by"])
    return factura
