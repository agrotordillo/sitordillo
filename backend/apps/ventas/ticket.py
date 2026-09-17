"""Arma el ticket de una `Venta` como texto plano ESC/POS.

Un mismo formato de puro texto (sin gráficos ni QR) imprime correctamente
tanto en las impresoras de impacto (Epson TM-U220, sin autocortador) como
en la térmica (Epson TM-T20IV, con autocortador) -las tres entienden
ESC/POS-. El ancho se ajusta por sucursal vía
`almacen.impresora_ancho_columnas`, ya que las impresoras de impacto y la
térmica no necesariamente comparten el mismo ancho de columnas.

El resultado son bytes ya codificados en CP850 (la página de códigos que
las Epson TM-U220/TM-T20IV usan para acentos y "ñ"), listos para mandarse
tal cual a QZ Tray como impresión raw.
"""

from textwrap import wrap

from django.utils import timezone

from apps.core.templatetags.core_extras import moneda

_ESC = "\x1b"
_GS = "\x1d"

_INIT = _ESC + "@"
_ALINEAR_IZQUIERDA = _ESC + "a" + "\x00"
_ALINEAR_CENTRO = _ESC + "a" + "\x01"
_NEGRITA_ON = _ESC + "E" + "\x01"
_NEGRITA_OFF = _ESC + "E" + "\x00"
_CODEPAGE_CP850 = _ESC + "t" + "\x02"
_CORTE_PAPEL = _GS + "V" + "\x01"

_CODIFICACION = "cp850"


def _nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.get_username()


def _fila(izquierda, derecha, ancho):
    """Una línea con `izquierda` pegada al margen y `derecha` alineado a la
    derecha, recortando `izquierda` si no alcanza el ancho disponible."""
    espacio = ancho - len(izquierda) - len(derecha)
    if espacio < 1:
        izquierda = izquierda[: max(ancho - len(derecha) - 1, 0)]
        espacio = 1
    return izquierda + " " * espacio + derecha + "\n"


def construir_ticket(venta, empresa=None):
    """Regresa el ticket de `venta` como bytes ESC/POS, replicando el mismo
    contenido que `ventas/venta_ticket.html` (encabezado, líneas,
    subtotal/IVA/total) en el ancho de columnas de la impresora de
    `venta.almacen`."""
    almacen = venta.almacen
    ancho = almacen.impresora_ancho_columnas
    separador = "-" * ancho + "\n"

    partes = [_INIT, _CODEPAGE_CP850, _ALINEAR_CENTRO]

    if empresa:
        partes.append(_NEGRITA_ON + empresa.display_name + "\n" + _NEGRITA_OFF)
        if empresa.rfc:
            partes.append(f"RFC: {empresa.rfc}\n")
        if empresa.telefono:
            partes.append(f"Tel: {empresa.telefono}\n")
    if almacen.direccion:
        partes.append(almacen.direccion + "\n")
    partes.append(almacen.nombre + "\n")

    partes.append(_ALINEAR_IZQUIERDA)
    partes.append(separador)
    if venta.turno:
        apertura_local = timezone.localtime(venta.turno.hora_apertura)
        partes.append(f"Turno: {venta.turno.fecha:%d/%m/%Y}  Apertura: {apertura_local:%H:%M}\n")
        partes.append(f"Punto de venta: {venta.turno.punto_venta.codigo} {venta.turno.punto_venta.nombre}\n")
        partes.append(f"Cajero: {_nombre_usuario(venta.turno.usuario)}\n")
    cotizacion_origen = getattr(venta, "cotizacion_origen", None)
    if cotizacion_origen and cotizacion_origen.created_by_id:
        partes.append(f"Vendedor (mostrador): {_nombre_usuario(cotizacion_origen.created_by)}\n")
    partes.append(separador)
    partes.append(f"Folio: {venta.folio}\n")
    partes.append(f"Impresión: {venta.veces_impreso}\n")
    fecha_local = timezone.localtime(venta.fecha_venta)
    partes.append(f"Fecha: {fecha_local:%d/%m/%Y}  Hora: {fecha_local:%H:%M}\n")
    partes.append(f"Cliente: {venta.cliente.display_name}\n")
    if venta.cliente.direccion:
        for renglon in wrap(venta.cliente.direccion, ancho) or [venta.cliente.direccion]:
            partes.append(renglon + "\n")
    if venta.pago_dividido:
        partes.append("Forma de pago (dividido):\n")
        for pago in venta.pagos.all():
            partes.append(_fila(f"  {pago.forma_pago.descripcion}", f"${moneda(pago.monto)}", ancho))
    else:
        partes.append(f"Forma de pago: {venta.forma_pago.descripcion}\n")
    partes.append(separador)

    for detalle in venta.detalles.all():
        producto = detalle.producto
        descuento_txt = f" (-{detalle.descuento}%)" if detalle.descuento else ""
        primera = f"{moneda(detalle.cantidad)}  {producto.sku}{descuento_txt}"
        partes.append(_fila(primera, f"${moneda(detalle.precio_unitario)}", ancho))

        abreviatura = producto.unidad_medida.abreviatura if producto.unidad_medida_id else ""
        importe_txt = f"${moneda(detalle.subtotal)}"
        # El primer renglón del nombre debe caber junto con la abreviatura Y
        # el importe -si se envolviera con el ancho completo, `_fila` lo
        # truncaría en silencio para que quepa el importe, perdiendo texto
        # en vez de pasarlo al siguiente renglón-.
        ancho_primer_renglon = max(ancho - len(abreviatura) - 1 - len(importe_txt) - 1, 10)
        primer_chunk = (wrap(producto.nombre, ancho_primer_renglon) or [producto.nombre])[0]
        resto_nombre = producto.nombre[len(primer_chunk):].strip()

        segunda = f"{abreviatura} {primer_chunk}".strip()
        partes.append(_fila(segunda, importe_txt, ancho))
        if resto_nombre:
            for renglon in wrap(resto_nombre, ancho):
                partes.append(renglon + "\n")

    partes.append(separador)
    partes.append(_fila("Subtotal:", f"${moneda(venta.importe_sin_impuesto)}", ancho))
    partes.append(_fila("IVA:", f"${moneda(venta.importe_iva)}", ancho))
    partes.append(_fila("IEPS:", f"${moneda(venta.importe_ieps)}", ancho))
    partes.append(_NEGRITA_ON)
    partes.append(_fila("TOTAL:", f"${moneda(venta.total)}", ancho))
    partes.append(_NEGRITA_OFF)

    if venta.observaciones:
        partes.append(separador)
        partes.append(venta.observaciones + "\n")

    partes.append(separador)
    partes.append(_fila("Peso en kilos:", moneda(venta.peso_total), ancho))
    partes.append(_fila("Volumen (m³):", moneda(venta.volumen_total), ancho))

    partes.append(separador)
    partes.append(_ALINEAR_CENTRO)
    partes.append("Gracias por su compra\n")
    partes.append("\n\n\n")
    partes.append(_CORTE_PAPEL)

    return "".join(partes).encode(_CODIFICACION, errors="replace")
