"""Descarga a Excel del reporte de comisión por colaborador."""
import re

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FUENTE = "Arial"
MONEDA = '$#,##0.00;-$#,##0.00;"-"'
PORCENTAJE = '0.00"%"'
CANTIDAD = '#,##0.##;-#,##0.##;"-"'
RELLENO = PatternFill("solid", fgColor="334155")
TOTAL = PatternFill("solid", fgColor="E2E8F0")


def _nombre(usuario):
    return usuario.get_full_name() or usuario.username


def _titulo_de_hoja(nombre, usados):
    """Nombre de hoja válido para Excel (31 caracteres, sin []:*?/\\) y único."""
    base = re.sub(r"[\[\]:*?/\\]", " ", nombre).strip()[:31] or "Colaborador"
    titulo, n = base, 2
    while titulo.lower() in usados:
        sufijo = f" ({n})"
        titulo, n = base[: 31 - len(sufijo)] + sufijo, n + 1
    usados.add(titulo.lower())
    return titulo


def _encabezado(hoja, fila, columnas):
    for i, (titulo, ancho) in enumerate(columnas, start=1):
        celda = hoja.cell(fila, i, titulo)
        celda.font = Font(name=FUENTE, bold=True, color="FFFFFF")
        celda.fill = RELLENO
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        hoja.column_dimensions[get_column_letter(i)].width = max(hoja.column_dimensions[get_column_letter(i)].width or 0, ancho)


def _escribir(hoja, fila, valores, formatos, negrita=False, relleno=None):
    for i, (valor, formato) in enumerate(zip(valores, formatos), start=1):
        celda = hoja.cell(fila, i, valor)
        celda.font = Font(name=FUENTE, size=10, bold=negrita)
        if formato:
            celda.number_format = formato
        if relleno:
            celda.fill = relleno


def libro_comisiones_ruta(contexto):
    """Un resumen (colaborador, vendido y comisión) y una hoja por
    colaborador: sus reglas con la base y la comisión del periodo, como los
    bloques del Excel con el que se pagan, y el detalle por venta. La
    comisión de cada regla es la suma de la de cada venta (redondeada venta
    por venta, igual que en pantalla); los totales van como fórmulas."""
    desde, hasta = contexto["periodo"]
    filtros = f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    if contexto.get("almacen"):
        filtros += f" · Sucursal: {contexto['almacen'].nombre}"
    filtros += f" · Generado el {timezone.localtime():%d/%m/%Y %H:%M}"

    libro = Workbook()
    resumen = libro.active
    resumen.title = "Resumen"
    resumen["A1"] = "Comisiones por colaborador"
    resumen["A1"].font = Font(name=FUENTE, size=14, bold=True)
    resumen["A2"] = filtros
    resumen["A2"].font = Font(name=FUENTE, size=9, italic=True)
    _encabezado(resumen, 4, [("Colaborador", 40), ("Plaza", 18), ("Vendido (sin IVA)", 18), ("Comisión", 16)])
    usados = {"resumen"}
    fila_resumen = 5
    for grupo in contexto["grupos"]:
        _escribir(
            resumen, fila_resumen,
            [_nombre(grupo["empleado"]), grupo["plaza"].nombre if grupo["plaza"] else "",
             float(grupo["total_importe"]), float(grupo["total_comision"])],
            [None, None, MONEDA, MONEDA],
        )
        _hoja_del_colaborador(libro, grupo, filtros, usados)
        fila_resumen += 1
    ultima = fila_resumen - 1
    _escribir(
        resumen, fila_resumen,
        ["Total", "", f"=SUM(C5:C{ultima})" if ultima >= 5 else 0, f"=SUM(D5:D{ultima})" if ultima >= 5 else 0],
        [None, None, MONEDA, MONEDA], negrita=True, relleno=TOTAL,
    )
    if contexto.get("sin_lista_precio"):
        resumen.cell(fila_resumen + 2, 1, (
            f"{contexto['sin_lista_precio']} línea(s) de venta con comisión configurada no se incluyeron por no "
            "tener registrada su lista de precio."
        )).font = Font(name=FUENTE, size=9, italic=True)
    resumen.freeze_panes = "A5"
    return libro


def _hoja_del_colaborador(libro, grupo, filtros, usados):
    hoja = libro.create_sheet(_titulo_de_hoja(_nombre(grupo["empleado"]), usados))
    hoja["A1"] = _nombre(grupo["empleado"]) + (f" · {grupo['plaza'].nombre}" if grupo["plaza"] else "")
    hoja["A1"].font = Font(name=FUENTE, size=13, bold=True)
    hoja["A2"] = filtros
    hoja["A2"].font = Font(name=FUENTE, size=9, italic=True)

    # Reglas
    _encabezado(hoja, 4, [
        ("Regla", 60), ("Vendido PUBLICO / M. MAYOREO", 18), ("%", 9), ("Vendido otras listas", 16),
        ("% otras", 9), ("Comisión", 14),
    ])
    fila = 5
    for totales in grupo["reglas"]:
        regla = totales["regla"]
        _escribir(
            hoja, fila,
            [regla.descripcion, float(totales["vendido_variable"]), float(regla.porcentaje),
             float(totales["vendido_otras"]), float(regla.porcentaje_otras_listas), float(totales["comision"])],
            [None, MONEDA, PORCENTAJE, MONEDA, PORCENTAJE, MONEDA],
        )
        fila += 1
    ultima = fila - 1
    _escribir(
        hoja, fila,
        ["Total", f"=SUM(B5:B{ultima})", "", f"=SUM(D5:D{ultima})", "", f"=SUM(F5:F{ultima})"],
        [None, MONEDA, None, MONEDA, None, MONEDA], negrita=True, relleno=TOTAL,
    )

    # Detalle por venta
    if not grupo["filas"]:
        return
    inicio = fila + 3
    hoja.cell(inicio - 1, 1, "Detalle por venta").font = Font(name=FUENTE, bold=True)
    columnas = [
        ("Fecha", 17), ("Folio", 16), ("Sucursal", 18), ("Vendió", 28), ("Producto", 40), ("SKU", 14),
        ("Lista", 14), ("Cantidad", 11), ("Importe (sin IVA)", 15), ("%", 9), ("Comisión", 13), ("Regla", 60),
    ]
    _encabezado(hoja, inicio, columnas)
    formatos = [None, None, None, None, None, None, None, CANTIDAD, MONEDA, PORCENTAJE, MONEDA, None]
    fila = inicio + 1
    for f in grupo["filas"]:
        venta = f["venta"]
        _escribir(hoja, fila, [
            timezone.localtime(venta.fecha_venta).strftime("%d/%m/%Y %H:%M"), venta.folio, venta.almacen.nombre,
            _nombre(f["vendedor"]) if f["vendedor"] else "", f["producto"].nombre, f["producto"].sku,
            f["lista_precio"].nombre if f["lista_precio"] else "", float(f["cantidad"]), float(f["importe"]),
            float(f["porcentaje"]), float(f["comision"]), f["regla"].descripcion,
        ], formatos)
        fila += 1
    _escribir(
        hoja, fila,
        ["Total", "", "", "", "", "", "", "", f"=SUM(I{inicio + 1}:I{fila - 1})", "", f"=SUM(K{inicio + 1}:K{fila - 1})", ""],
        formatos, negrita=True, relleno=TOTAL,
    )
    hoja.freeze_panes = "A5"
