import base64
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from .facturama_client import FacturamaClient, FacturamaError
from .models import Empresa, Factura, FacturaGlobal

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")

# RFC genérico que exige el SAT como receptor de una factura global (CFDI
# que concentra las ventas a clientes sin RFC propio, "Público en
# general"). Nunca es el RFC de un cliente real.
RFC_PUBLICO_GENERAL = "XAXX010101000"


def _desglosar_linea(detalle):
    """Desglosa impuestos de una línea de venta asumiendo que
    `precio_unitario` ya incluye todos los impuestos (IVA e IEPS, si
    aplican) — así se etiquetan los precios al público en México. El IEPS
    se calcula sobre la base sin impuestos, y el IVA sobre (base + IEPS),
    que es la forma fiscalmente correcta cuando ambos aplican al mismo
    producto.

    Con descuento, todo va sin impuestos, como lo pide el CFDI (B31 en
    docs/AUDITORIA.md): `importe` es el valor de la línea antes del
    descuento, `descuento` lo que se rebaja, y `base` (= importe -
    descuento) es sobre lo que se calculan los impuestos. Así el total de
    la línea, importe - descuento + impuestos, es el precio cobrado."""
    producto = detalle.producto
    cantidad = detalle.cantidad
    descuento_pct = detalle.descuento or Decimal("0")

    importe_con_impuestos = (detalle.precio_unitario * cantidad).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    descuento_con_impuestos = (importe_con_impuestos * descuento_pct / Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    tasa_iva = (producto.tasa_iva / Decimal("100")) if producto.tipo_iva == producto.TipoIVA.GRAVADO else Decimal("0")
    tasa_ieps = (producto.tasa_ieps / Decimal("100")) if producto.aplica_ieps and producto.tasa_ieps else Decimal("0")

    factor = (Decimal("1") + tasa_ieps) * (Decimal("1") + tasa_iva)
    importe = (importe_con_impuestos / factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    base = ((importe_con_impuestos - descuento_con_impuestos) / factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    # Por diferencia, no recalculado: importe - descuento debe dar la base exacta.
    descuento = importe - base
    ieps_monto = (base * tasa_ieps).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    iva_monto = ((base + ieps_monto) * tasa_iva).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    precio_unitario_sin_impuestos = (importe / cantidad) if cantidad else importe

    return {
        "producto": producto,
        "cantidad": cantidad,
        "precio_unitario_sin_impuestos": precio_unitario_sin_impuestos,
        "importe": importe,
        "descuento": descuento,
        "base": base,
        "tasa_iva": tasa_iva,
        "iva_monto": iva_monto,
        "tasa_ieps": tasa_ieps,
        "ieps_monto": ieps_monto,
    }


def _construir_item_cfdi(detalle):
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
    total_linea = d["importe"] - d["descuento"] + total_impuestos

    item = {
        "ProductCode": producto.clave_prod_serv_sat.clave,
        "IdentificationNumber": producto.sku,
        "Description": producto.nombre,
        # Facturama exige longitud 1-20 y no acepta '|'; el nombre oficial
        # del SAT puede ser más largo, así que se trunca defensivamente.
        "Unit": producto.clave_unidad_sat.nombre.replace("|", "")[:20],
        "UnitCode": producto.clave_unidad_sat.clave,
        "UnitPrice": float(d["precio_unitario_sin_impuestos"]),
        "Quantity": float(d["cantidad"]),
        "Subtotal": float(d["importe"]),
        "Discount": float(d["descuento"]),
        "Total": float(total_linea),
        "TaxObject": "02" if taxes else "01",
    }
    # Facturama rechaza la solicitud si el nodo Taxes está presente
    # (aunque sea una lista vacía) cuando TaxObject no es "02": no basta
    # con mandar taxes=[], la clave "Taxes" no debe existir en absoluto.
    if taxes:
        item["Taxes"] = taxes
    return item


def construir_payload_cfdi(factura):
    venta = factura.venta
    cliente = venta.cliente

    items = [_construir_item_cfdi(d) for d in venta.detalles.select_related("producto")]

    return {
        # Serie/Folio no se envían: Facturama los asigna según la serie
        # configurada en el perfil fiscal de la cuenta (ver
        # https://apisandbox.facturama.mx/guias/perfil-fiscal). Nuestro
        # folio interno (Factura.numero_folio) es solo para referencia
        # antes de timbrar; se sincroniza con lo que Facturama devuelva.
        "Currency": factura.moneda,
        "ExpeditionPlace": factura.lugar_expedicion,
        "CfdiType": "I",
        # "99 Por definir" (misma clave que ventas.Venta.CLAVE_CREDITO)
        # cuando el cobro se dividió en varias formas de pago
        # (venta.forma_pago vacío, ver Venta.pago_dividido): el SAT no
        # tiene una clave de "pago mixto", así que se declara ésta -se
        # sigue facturando por el total completo, el desglose real queda
        # en el registro interno de la venta (VentaPago)-.
        "PaymentForm": venta.forma_pago.clave if venta.forma_pago_id else "99",
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
    from apps.ventas.models import Venta

    # Con la venta bloqueada: dos "Generar factura" a la vez no deben chocar
    # con la relación 1 a 1 (error 500); el segundo la encuentra ya hecha.
    venta = Venta.objects.select_for_update().get(pk=venta.pk)
    if Factura.objects.filter(venta=venta).exists():
        raise ValueError("Esta venta ya tiene una factura generada.")

    empresa = Empresa.objects.first()
    if not empresa:
        raise ValueError("Registra primero los datos fiscales de la empresa.")

    serie = serie or empresa.serie_default
    # Si full_clean() rechaza la factura, la transacción se revierte y el
    # folio tomado regresa con ella: no quedan huecos en la numeración.
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
    factura.full_clean()
    factura.save()
    return factura


# --- Timbrado (común a Factura y FacturaGlobal) --------------------------
#
# Un CFDI timbrado es un documento legal ante el SAT: el riesgo a evitar no
# es que falle el timbrado, sino emitir dos para la misma venta/turno. Por
# eso el timbrado va en tres pasos:
#   1. _reservar_para_timbrar: transacción corta que bloquea la fila,
#      confirma que se puede timbrar (Borrador o Error) y la deja en
#      TIMBRANDO. Un segundo intento simultáneo (doble clic, dos usuarios)
#      espera al primero y después la encuentra en TIMBRANDO: se rechaza.
#   2. La llamada a Facturama, ya fuera de cualquier transacción (puede
#      tardar hasta 90 s; no se retiene una conexión ni un bloqueo).
#   3. Registrar el resultado. Si Facturama rechazó la solicitud (fallo
#      cierto) queda en ERROR y se puede reintentar; si la respuesta no
#      llegó o llegó ilegible (fallo incierto) se queda en TIMBRANDO hasta
#      que alguien verifique en Facturama y la libere (liberar_timbrado).

# Más que el timeout del cliente (90 s): antes de eso, un comprobante en
# TIMBRANDO puede seguir esperando la respuesta y no se debe liberar.
SEGUNDOS_MINIMOS_PARA_LIBERAR = 120

MENSAJE_VERIFICAR_EN_FACTURAMA = (
    "Revisa en el portal de Facturama antes de reintentar; si no aparece, un administrador "
    "puede liberarlo para volver a intentarlo."
)
MENSAJE_TIMBRADO_INCIERTO = (
    "Facturama no confirmó el resultado del timbrado: el comprobante pudo haberse timbrado. "
    + MENSAJE_VERIFICAR_EN_FACTURAMA
)


def _nombre(modelo):
    return modelo._meta.verbose_name.lower()


def _guardar(comprobante, **campos):
    for campo, valor in campos.items():
        setattr(comprobante, campo, valor)
    comprobante.save(update_fields=[*campos, "updated_at", "updated_by"])


def _reservar_para_timbrar(modelo, pk):
    with transaction.atomic():
        comprobante = modelo.objects.select_for_update().get(pk=pk)
        Estatus = modelo.Estatus
        if comprobante.estatus == Estatus.TIMBRADA:
            raise ValueError(f"La {_nombre(modelo)} {comprobante.serie_folio} ya está timbrada.")
        if comprobante.estatus == Estatus.CANCELADA:
            raise ValueError(f"La {_nombre(modelo)} {comprobante.serie_folio} está cancelada; no se puede timbrar.")
        if comprobante.estatus == Estatus.TIMBRANDO:
            raise ValueError(
                f"La {_nombre(modelo)} {comprobante.serie_folio} ya se está timbrando o quedó pendiente de "
                f"confirmar con Facturama. {MENSAJE_VERIFICAR_EN_FACTURAMA}"
            )

        campos = {"estatus": Estatus.TIMBRANDO, "mensaje_error": ""}
        # El lugar de expedición se copia de Empresa.codigo_postal al crear el
        # borrador; si el primer intento falló porque ese CP no coincidía con
        # el registrado en Facturama y se corrigió después en "Datos de la
        # empresa", el reintento usa el valor ya corregido.
        empresa = Empresa.objects.first()
        if empresa and comprobante.lugar_expedicion != empresa.codigo_postal:
            campos["lugar_expedicion"] = empresa.codigo_postal
        _guardar(comprobante, **campos)
    return comprobante


def _registrar_timbre(comprobante, data):
    complemento = data.get("Complement") or {}
    timbre = complemento.get("TaxStamp") or {}
    _guardar(
        comprobante,
        facturama_id=str(data.get("Id") or ""),
        uuid_fiscal=str(timbre.get("Uuid") or data.get("Uuid") or ""),
        # La serie/folio que asignó Facturama (su perfil fiscal) se guarda
        # aparte: la serie/numero_folio internos no se tocan, así nunca
        # chocan con los de otro comprobante (ver SerieFolioMixin).
        serie_facturama=str(data.get("Serie") or "")[:25],
        folio_facturama=str(data.get("Folio") or "")[:40],
        estatus=type(comprobante).Estatus.TIMBRADA,
        fecha_timbrado=timezone.now(),
        mensaje_error="",
    )


def _timbrar(modelo, comprobante, construir_payload):
    comprobante = _reservar_para_timbrar(modelo, comprobante.pk)
    Estatus = modelo.Estatus

    try:
        payload = construir_payload(comprobante)
    except Exception as e:
        # Todavía no se mandó nada a Facturama: se puede reintentar sin riesgo.
        mensaje = f"No se pudo armar el comprobante para timbrarlo: {e}"
        _guardar(comprobante, estatus=Estatus.ERROR, mensaje_error=mensaje)
        raise ValueError(mensaje) from e

    try:
        data = FacturamaClient().crear_cfdi(payload)
    except FacturamaError as e:
        if e.incierto:
            logger.warning("Timbrado incierto de %s %s: %s", _nombre(modelo), comprobante.pk, e)
            _guardar(comprobante, mensaje_error=f"{MENSAJE_TIMBRADO_INCIERTO} Detalle: {e}")
        else:
            _guardar(comprobante, estatus=Estatus.ERROR, mensaje_error=str(e))
        raise
    except Exception as e:
        # Un fallo inesperado del lado de aquí: no se sabe si la solicitud
        # alcanzó a salir, así que se trata como incierto (se queda en
        # TIMBRANDO, nunca se reintenta solo).
        logger.exception("Error inesperado al timbrar %s %s", _nombre(modelo), comprobante.pk)
        _guardar(comprobante, mensaje_error=f"{MENSAJE_TIMBRADO_INCIERTO} Detalle: {e}")
        raise FacturamaError(str(e), incierto=True) from e

    try:
        _registrar_timbre(comprobante, data)
    except Exception:
        # El CFDI ya existe en Facturama: se deja constancia en el log para
        # poder registrarlo a mano. El comprobante sigue en TIMBRANDO, así
        # que nadie puede volver a timbrarlo por error.
        logger.exception(
            "CFDI timbrado en Facturama pero no se pudo registrar: %s %s, Id=%s, UUID=%s",
            _nombre(modelo), comprobante.pk, data.get("Id"),
            (data.get("Complement") or {}).get("TaxStamp", {}).get("Uuid"),
        )
        raise
    logger.info(
        "Timbrado %s %s: Id=%s, UUID=%s", _nombre(modelo), comprobante.pk,
        comprobante.facturama_id, comprobante.uuid_fiscal,
    )
    return comprobante, data


def liberar_timbrado(modelo, comprobante):
    """Regresa a ERROR (para poder reintentar) un comprobante que se quedó en
    TIMBRANDO porque Facturama no confirmó el resultado. Solo debe hacerlo
    quien ya verificó en el portal de Facturama que NO se timbró; no se
    permite mientras el intento original todavía puede estar esperando
    respuesta (ver SEGUNDOS_MINIMOS_PARA_LIBERAR)."""
    with transaction.atomic():
        comprobante = modelo.objects.select_for_update().get(pk=comprobante.pk)
        if comprobante.estatus != modelo.Estatus.TIMBRANDO:
            raise ValueError("Solo se puede liberar un comprobante que quedó en Timbrando.")
        transcurrido = (timezone.now() - comprobante.updated_at).total_seconds()
        if transcurrido < SEGUNDOS_MINIMOS_PARA_LIBERAR:
            raise ValueError(
                "El timbrado todavía puede estar en curso; espera un par de minutos y verifica en Facturama "
                "antes de liberarlo."
            )
        _guardar(
            comprobante,
            estatus=modelo.Estatus.ERROR,
            mensaje_error="Liberado manualmente para reintentar (se verificó en Facturama que no se timbró).",
        )
    return comprobante


def timbrar_factura(factura):
    return _timbrar(Factura, factura, construir_payload_cfdi)


def _validar_timbrada(factura):
    if factura.estatus != Factura.Estatus.TIMBRADA or not factura.facturama_id:
        raise ValueError("Esta factura todavía no está timbrada.")


def obtener_pdf(factura):
    _validar_timbrada(factura)
    contenido_b64 = FacturamaClient().obtener_pdf_base64(factura.facturama_id)
    return base64.b64decode(contenido_b64)


def obtener_xml(factura):
    _validar_timbrada(factura)
    contenido_b64 = FacturamaClient().obtener_xml_base64(factura.facturama_id)
    return base64.b64decode(contenido_b64)


def cancelar_factura(factura, motivo="02", uuid_reemplazo=None):
    """Bloquea la factura durante la cancelación: dos cancelaciones al mismo
    tiempo no mandan dos solicitudes a Facturama."""
    with transaction.atomic():
        factura = Factura.objects.select_for_update().get(pk=factura.pk)
        _validar_timbrada(factura)
        FacturamaClient().cancelar_cfdi(factura.facturama_id, motivo=motivo, uuid_reemplazo=uuid_reemplazo)
        _guardar(factura, estatus=Factura.Estatus.CANCELADA)
    return factura


# --- Factura global (cierre fiscal de "Público en general" por turno) ----

def ventas_elegibles_para_global(turno):
    """Ventas de este turno a "Público en general" que todavía no tienen
    factura propia (el cliente la pidió aparte, ver Venta.factura) ni ya
    quedaron en otra factura global. Las remisiones (Venta.es_remision)
    nunca entran aquí: por definición no tienen impacto fiscal."""
    from apps.clientes.models import Cliente

    publico = Cliente.publico_general()
    if publico is None:
        return turno.ventas.none()
    return (
        turno.ventas.filter(cliente=publico, factura__isnull=True, factura_global__isnull=True)
        .filter(es_remision=False)
        .select_related("cliente")
    )


def _forma_pago_predominante(ventas):
    """El SAT no admite "99 Por definir" combinado con método de pago PUE
    (pago ya recibido, nunca diferido) -lo confirmó el sandbox de
    Facturama al rechazar la primera versión de este comprobante-, así
    que una factura global que concentra ventas con formas de pago
    distintas (unas en efectivo, otras con tarjeta) no puede declarar
    "99" como hacía Factura con una venta de cobro dividido. Se resuelve
    con el mismo criterio que ya usaba el sistema anterior (scvweb) para
    este caso: se declara la forma de pago que acumuló el monto más alto
    en el periodo. Cuenta tanto las ventas con una sola forma de pago
    como el desglose de las que se cobraron divididas (ver VentaPago).
    Devuelve None solo si `ventas` viene vacío."""
    montos = {}
    for venta in ventas:
        if venta.pago_dividido:
            for pago in venta.pagos.all():
                montos[pago.forma_pago_id] = montos.get(pago.forma_pago_id, Decimal("0.00")) + pago.monto
        else:
            montos[venta.forma_pago_id] = montos.get(venta.forma_pago_id, Decimal("0.00")) + venta.total
    if not montos:
        return None
    from apps.fiscal.models import FormaPago
    forma_pago_id = max(montos, key=montos.get)
    return FormaPago.objects.get(pk=forma_pago_id)


def _construir_item_cfdi_global(venta):
    """Una sola línea genérica por VENTA -no una por producto, como sí
    hace construir_payload_cfdi para una Factura individual-: clave SAT
    "01010101" (No existe en el catálogo) y unidad "ACT" (Actividad),
    mismo criterio que ya usaba el sistema anterior (scvweb) para la
    factura global, en vez de exponer el detalle real de cada venta a
    Público en general en un solo CFDI que las concentra todas. Los
    impuestos sí se calculan de verdad -agregados de las líneas reales de
    esa venta, agrupados por tasa- y se reportan bajo esta línea
    genérica."""
    ivas = {}
    ieps = {}
    importe_total = Decimal("0.00")
    descuento_total = Decimal("0.00")
    for detalle in venta.detalles.select_related("producto"):
        d = _desglosar_linea(detalle)
        importe_total += d["importe"]
        descuento_total += d["descuento"]
        if d["tasa_iva"] > 0:
            acumulado = ivas.setdefault(d["tasa_iva"], {"base": Decimal("0.00"), "monto": Decimal("0.00")})
            acumulado["base"] += d["base"] + d["ieps_monto"]
            acumulado["monto"] += d["iva_monto"]
        if d["tasa_ieps"] > 0:
            acumulado = ieps.setdefault(d["tasa_ieps"], {"base": Decimal("0.00"), "monto": Decimal("0.00")})
            acumulado["base"] += d["base"]
            acumulado["monto"] += d["ieps_monto"]

    taxes = []
    for tasa, acumulado in ivas.items():
        taxes.append({
            "Total": float(acumulado["monto"]),
            "Name": "IVA",
            "Base": float(acumulado["base"]),
            "Rate": float(tasa),
            "IsRetention": False,
        })
    for tasa, acumulado in ieps.items():
        taxes.append({
            "Total": float(acumulado["monto"]),
            "Name": "IEPS",
            "Base": float(acumulado["base"]),
            "Rate": float(tasa),
            "IsRetention": False,
        })

    total_impuestos = sum((Decimal(str(t["Total"])) for t in taxes), Decimal("0.00"))
    total_linea = importe_total - descuento_total + total_impuestos

    item = {
        "ProductCode": "01010101",
        "IdentificationNumber": venta.folio,
        "Description": "Venta",
        "Unit": "Actividad",
        "UnitCode": "ACT",
        "UnitPrice": float(importe_total),
        "Quantity": 1,
        "Subtotal": float(importe_total),
        "Discount": float(descuento_total),
        "Total": float(total_linea),
        "TaxObject": "02" if taxes else "01",
    }
    if taxes:
        item["Taxes"] = taxes
    return item


def construir_payload_cfdi_global(factura_global):
    items = [_construir_item_cfdi_global(venta) for venta in factura_global.ventas.all()]

    return {
        "Currency": factura_global.moneda,
        "ExpeditionPlace": factura_global.lugar_expedicion,
        "CfdiType": "I",
        "PaymentForm": factura_global.forma_pago.clave,
        "PaymentMethod": factura_global.metodo_pago.clave,
        "Exportation": "01",
        # Nodo que exige el SAT para un "Comprobante Global": de qué
        # periodo son las ventas que se están concentrando aquí. "01" es
        # Diario -ver la nota en FacturaGlobal sobre el supuesto de un
        # turno de caja = un día-.
        "GlobalInformation": {
            "Periodicity": "01",
            "Months": factura_global.periodo_mes,
            "Year": str(factura_global.periodo_anio),
        },
        "Receiver": {
            "Rfc": RFC_PUBLICO_GENERAL,
            "Name": "PUBLICO EN GENERAL",
            "CfdiUse": "S01",
            "FiscalRegime": "616",
            "TaxZipCode": factura_global.lugar_expedicion,
        },
        "Items": items,
    }


@transaction.atomic
def generar_factura_global(turno, metodo_pago, observaciones=""):
    from apps.products.models import Turno
    from apps.ventas.models import Venta

    # Turno y ventas bloqueados: dos cierres fiscales simultáneos del mismo
    # turno no chocan con la relación 1 a 1 (error 500), y ninguna de esas
    # ventas puede recibir a la vez una factura individual (generar_factura
    # bloquea la misma venta).
    turno = Turno.objects.select_for_update().get(pk=turno.pk)
    if FacturaGlobal.objects.filter(turno=turno).exists():
        raise ValueError("Este turno ya tiene una factura global generada.")

    ventas = list(
        ventas_elegibles_para_global(turno)
        .select_for_update(of=("self",))
        .order_by("pk")
        .prefetch_related("pagos__forma_pago")
    )
    if not ventas:
        raise ValueError("No hay ventas a Público en general sin facturar en este turno.")

    forma_pago = _forma_pago_predominante(ventas)

    empresa = Empresa.objects.first()
    if not empresa:
        raise ValueError("Registra primero los datos fiscales de la empresa.")

    # Mismo folio consecutivo que una Factura individual (Empresa solo
    # lleva un contador); la "G" en la serie es solo para distinguirlas a
    # simple vista en los listados, no cambia la numeración fiscal real
    # -Facturama/el SAT solo exigen que serie+folio sea único-.
    serie = f"{empresa.serie_default}G"
    # Si full_clean() la rechaza, la transacción se revierte y el folio
    # regresa con ella (ver Empresa.tomar_siguiente_folio).
    numero_folio = empresa.tomar_siguiente_folio()

    factura_global = FacturaGlobal(
        turno=turno,
        serie=serie,
        numero_folio=numero_folio,
        metodo_pago=metodo_pago,
        forma_pago=forma_pago,
        lugar_expedicion=empresa.codigo_postal,
        periodo_mes=f"{turno.fecha.month:02d}",
        periodo_anio=turno.fecha.year,
        observaciones=observaciones,
    )
    factura_global.full_clean()
    factura_global.save()
    Venta.objects.filter(pk__in=[v.pk for v in ventas]).update(factura_global=factura_global)
    return factura_global


def timbrar_factura_global(factura_global):
    return _timbrar(FacturaGlobal, factura_global, construir_payload_cfdi_global)
