from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.fiscal.models import FormaPago
from apps.products.models import Almacen, Producto
from apps.proveedores.models import Proveedor

from .models import OrdenCompra, OrdenCompraDetalle

# CFDI puede venir en 3.3 o 4.0; el namespace cambia entre versiones pero la
# estructura de Conceptos/Impuestos es prácticamente la misma para lo que
# necesitamos aquí.
NAMESPACES_CFDI = {
    "4.0": "http://www.sat.gob.mx/cfd/4",
    "3.3": "http://www.sat.gob.mx/cfd/3",
}
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"

# Claves de impuesto del catálogo SAT c_Impuesto.
CLAVE_IVA = "002"
CLAVE_IEPS = "003"
CLAVE_ISR = "001"


class CFDIImportError(ValueError):
    """Error de negocio al importar un CFDI (no de formato/parseo XML)."""


def _dec(valor, default="0"):
    if valor in (None, ""):
        return Decimal(default)
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return Decimal(default)


def _detectar_namespace(root):
    tag = root.tag  # p.ej. "{http://www.sat.gob.mx/cfd/4}Comprobante"
    for version, uri in NAMESPACES_CFDI.items():
        if tag == f"{{{uri}}}Comprobante":
            return version, uri
    raise CFDIImportError("El archivo no parece ser un CFDI 3.3 o 4.0 válido (nodo raíz Comprobante no encontrado).")


def _sumar_impuestos(comprobante, ns, clave, tipo):
    """Suma los importes de traslados o retenciones de una clave de
    impuesto (IVA/IEPS/ISR) a nivel comprobante. `tipo` es "Traslados" o
    "Retenciones"."""
    total = Decimal("0.00")
    impuestos = comprobante.find(f"cfdi:Impuestos", ns)
    if impuestos is None:
        return total
    contenedor = impuestos.find(f"cfdi:{tipo}", ns)
    if contenedor is None:
        return total
    etiqueta = "Traslado" if tipo == "Traslados" else "Retencion"
    for nodo in contenedor.findall(f"cfdi:{etiqueta}", ns):
        if nodo.get("Impuesto") == clave:
            total += _dec(nodo.get("Importe"))
    return total


def _buscar_producto(codigo_proveedor, sku_alterno):
    """Empareja un concepto del CFDI con un Producto: primero por el código
    del proveedor (Producto.codigo_proveedor, que es justo para esto),
    luego por SKU interno como respaldo."""
    codigo = (codigo_proveedor or "").strip()
    if codigo:
        producto = (
            Producto.objects.filter(is_active=True, codigo_proveedor__iexact=codigo)
            .exclude(tipo=Producto.TipoProducto.PAQUETE)
            .first()
        )
        if producto:
            return producto
    sku = (sku_alterno or "").strip()
    if sku:
        return (
            Producto.objects.filter(is_active=True, sku__iexact=sku)
            .exclude(tipo=Producto.TipoProducto.PAQUETE)
            .first()
        )
    return None


@transaction.atomic
def importar_cfdi_compra(archivo):
    """Crea una OrdenCompra (borrador) a partir del XML de un CFDI de tipo
    Ingreso emitido por un proveedor. Usa el Importe/Descuento que cada
    concepto ya trae declarado en el XML para calcular el precio neto por
    línea (Importe - Descuento) / Cantidad — el mismo dato que declara la
    factura, sin redondeos de por medio, en vez de recalcularlo desde un
    % general o desde el precio impreso.

    Devuelve (orden, no_encontrados) donde `no_encontrados` es una lista de
    dicts {codigo, descripcion} de los conceptos que no se pudieron
    emparejar con ningún Producto — esas líneas no se agregan, hay que
    completarlas a mano después."""
    try:
        root = ElementTree.parse(archivo).getroot()
    except ElementTree.ParseError as exc:
        raise CFDIImportError(f"El archivo no es un XML válido: {exc}") from exc

    version, uri = _detectar_namespace(root)
    ns = {"cfdi": uri}

    emisor = root.find("cfdi:Emisor", ns)
    if emisor is None:
        raise CFDIImportError("El CFDI no trae los datos del emisor (proveedor).")
    rfc_emisor = (emisor.get("Rfc") or "").strip()

    proveedor = Proveedor.objects.filter(is_active=True, rfc__iexact=rfc_emisor).first()
    if proveedor is None:
        raise CFDIImportError(
            f"No hay ningún proveedor activo con el RFC {rfc_emisor}. Da de alta al proveedor antes de cargar el CFDI."
        )

    complemento = root.find("cfdi:Complemento", ns)
    uuid_cfdi = None
    fecha_timbrado = None
    if complemento is not None:
        timbre = complemento.find(f"{{{NS_TFD}}}TimbreFiscalDigital")
        if timbre is not None:
            uuid_cfdi = timbre.get("UUID")
            fecha_timbrado = timbre.get("FechaTimbrado")

    if uuid_cfdi and OrdenCompra.objects.filter(cfdi_uuid__iexact=uuid_cfdi).exists():
        raise CFDIImportError(f"Este CFDI (folio fiscal {uuid_cfdi}) ya se había cargado antes.")

    fecha_texto = root.get("Fecha") or fecha_timbrado
    fecha_dt = parse_datetime(fecha_texto) if fecha_texto else None
    fecha_orden = fecha_dt.date() if fecha_dt else None

    serie = root.get("Serie", "")
    folio = root.get("Folio", "")
    documento = f"{serie}{folio}".strip() or (uuid_cfdi or "")

    clave_forma_pago = root.get("FormaPago", "").strip()
    forma_pago = FormaPago.objects.filter(clave=clave_forma_pago).first() if clave_forma_pago else None

    metodo_pago_cfdi = root.get("MetodoPago", "")
    estado_pago = (
        OrdenCompra.EstadoPago.CREDITO if metodo_pago_cfdi == "PPD" else OrdenCompra.EstadoPago.CONTADO
    )

    almacen_cedis = Almacen.objects.filter(is_active=True, tipo=Almacen.Tipo.CEDIS).first()

    orden = OrdenCompra(
        proveedor=proveedor,
        almacen_destino=almacen_cedis,
        fecha_orden=fecha_orden,
        estatus=OrdenCompra.Estatus.BORRADOR,
        es_fiscal=True,
        documento=documento,
        cfdi_uuid=uuid_cfdi or None,
        estado_pago=estado_pago,
        forma_pago=forma_pago,
        # El descuento ya viene neteado línea por línea (ver abajo), así que
        # el % general de la orden se deja en 0 para no restarlo dos veces.
        descuento_pct=Decimal("0.00"),
        iva=_sumar_impuestos(root, ns, CLAVE_IVA, "Traslados"),
        ieps=_sumar_impuestos(root, ns, CLAVE_IEPS, "Traslados"),
        retencion_iva=_sumar_impuestos(root, ns, CLAVE_IVA, "Retenciones"),
        retencion_isr=_sumar_impuestos(root, ns, CLAVE_ISR, "Retenciones"),
        observaciones=f"Generada al cargar el CFDI {uuid_cfdi}." if uuid_cfdi else "Generada al cargar un CFDI.",
    )
    orden.full_clean()
    orden.save()

    conceptos = root.find("cfdi:Conceptos", ns)
    no_encontrados = []
    if conceptos is not None:
        for concepto in conceptos.findall("cfdi:Concepto", ns):
            cantidad = _dec(concepto.get("Cantidad"), "0")
            importe = _dec(concepto.get("Importe"), "0")
            descuento = _dec(concepto.get("Descuento"), "0")
            descripcion = concepto.get("Descripcion", "")
            codigo_proveedor = concepto.get("NoIdentificacion", "")

            if cantidad <= 0:
                continue

            importe_neto = importe - descuento
            precio_neto = (importe_neto / cantidad).quantize(Decimal("0.01"))

            producto = _buscar_producto(codigo_proveedor, codigo_proveedor)
            if producto is None:
                no_encontrados.append({"codigo": codigo_proveedor, "descripcion": descripcion})
                continue

            detalle = OrdenCompraDetalle(
                orden_compra=orden,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=precio_neto,
            )
            detalle.full_clean()
            detalle.save()

    return orden, no_encontrados
