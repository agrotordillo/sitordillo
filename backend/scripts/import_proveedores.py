"""
Script de una sola vez para cargar proveedores desde datos/proveedores.xlsx.

Uso (desde backend/, con el venv del proyecto):
    C:\\proyectos\\env\\Scripts\\python.exe scripts\\import_proveedores.py

Columnas esperadas en la hoja "Hoja1":
    tipo, rfc, nombre_fiscal, nombre_comercial, nombre_contacto, descuento,
    credito_autorizado, limite_credito, dias_credito, observaciones,
    lista_precio (ignorada, sin campo equivalente en el modelo),
    sat_cfdi_3_3_c_regimenfiscal (clave SAT de RegimenFiscal)

tipo_persona se infiere por longitud del RFC normalizado (13 = física, 12 = moral).
Cada fila se valida con Proveedor.full_clean(); las filas que no pasan
validación (RFC inválido, régimen fiscal incompatible con el tipo de persona,
límite/días de crédito sin crédito autorizado, RFC duplicado, etc.) se
omiten y se listan al final para revisión manual.

Caso especial: en el archivo fuente, el régimen SAT 612 (Personas Físicas con
Actividades Empresariales y Profesionales) se usó como valor por defecto para
casi todos los proveedores, incluidos varios con RFC de persona moral (12
caracteres), para quienes ese régimen no es válido. En esos casos el script
sustituye el régimen por 601 (General de Ley Personas Morales) y lo reporta
como ajuste, en vez de omitir la fila.
"""
import os
import re
import sys
from pathlib import Path

import django

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.core.exceptions import ValidationError  # noqa: E402

from apps.fiscal.models import RegimenFiscal  # noqa: E402
from apps.proveedores.models import Proveedor  # noqa: E402

EXCEL_PATH = Path(r"C:\proyectos\django\sitordillo\datos\proveedores.xlsx")
SHEET_NAME = "Hoja1"

RFC_PATTERN = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
PLACEHOLDER_VALUES = {"", ".", "NULL"}


def normalize_rfc(raw):
    if raw is None:
        return ""
    return re.sub(r"[\s\-]", "", str(raw)).upper()


def clean_text(raw):
    if raw is None:
        return ""
    value = str(raw).strip()
    return "" if value.upper() in PLACEHOLDER_VALUES else value


def main():
    import openpyxl

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb[SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))
    header, data_rows = rows[0], rows[1:]

    regimenes_cache = {r.clave: r for r in RegimenFiscal.objects.all()}
    rfcs_procesados_en_archivo = set()

    creados = 0
    omitidos = []
    ajustados = []

    for excel_row_num, row in enumerate(data_rows, start=2):
        tipo, rfc_raw, nombre_fiscal, nombre_comercial, nombre_contacto, descuento, \
            credito_autorizado, limite_credito, dias_credito, observaciones, \
            _lista_precio, sat_cfdi = row

        if (tipo or "").strip().upper() != "PROVEEDOR":
            continue

        rfc = normalize_rfc(rfc_raw)

        if len(rfc) not in (12, 13) or not RFC_PATTERN.match(rfc):
            omitidos.append((excel_row_num, rfc_raw, "RFC con formato inválido"))
            continue

        if rfc in rfcs_procesados_en_archivo:
            omitidos.append((excel_row_num, rfc_raw, "RFC duplicado dentro del archivo"))
            continue

        if Proveedor.objects.filter(rfc=rfc).exists():
            omitidos.append((excel_row_num, rfc_raw, "Ya existe un proveedor con este RFC"))
            continue

        if sat_cfdi is None:
            omitidos.append((excel_row_num, rfc_raw, "Sin clave de régimen fiscal SAT"))
            continue

        regimen = regimenes_cache.get(str(int(sat_cfdi)))
        if regimen is None:
            omitidos.append((excel_row_num, rfc_raw, f"Clave de régimen fiscal SAT {sat_cfdi} no existe en el catálogo"))
            continue

        tipo_persona = Proveedor.TipoPersona.FISICA if len(rfc) == 13 else Proveedor.TipoPersona.MORAL

        if tipo_persona == Proveedor.TipoPersona.MORAL and not regimen.aplica_moral:
            regimen_601 = regimenes_cache.get("601")
            if regimen_601 is not None:
                ajustados.append((excel_row_num, rfc_raw, f"régimen {regimen.clave} -> 601 (persona moral, régimen original no aplica)"))
                regimen = regimen_601

        proveedor = Proveedor(
            tipo_persona=tipo_persona,
            rfc=rfc,
            nombre_fiscal=clean_text(nombre_fiscal),
            nombre_comercial=clean_text(nombre_comercial),
            regimen_fiscal=regimen,
            tiene_credito=(str(credito_autorizado or "").strip().upper() == "SI"),
            limite_credito=limite_credito or 0,
            dias_credito=dias_credito or 0,
            descuento=descuento or 0,
            contacto_nombre=clean_text(nombre_contacto),
            observaciones=clean_text(observaciones),
        )

        try:
            proveedor.full_clean()
        except ValidationError as exc:
            omitidos.append((excel_row_num, rfc_raw, "; ".join(f"{k}: {', '.join(v)}" for k, v in exc.message_dict.items())))
            continue

        proveedor.save()
        rfcs_procesados_en_archivo.add(rfc)
        creados += 1

    print(f"Proveedores creados: {creados}")
    print(f"Filas con régimen fiscal ajustado a 601: {len(ajustados)}")
    print(f"Filas omitidas: {len(omitidos)}")
    if ajustados:
        print("\nDetalle de filas con régimen ajustado:")
        for excel_row_num, rfc_raw, motivo in ajustados:
            print(f"  fila {excel_row_num} | rfc original: {rfc_raw!r} | {motivo}")
    if omitidos:
        print("\nDetalle de filas omitidas:")
        for excel_row_num, rfc_raw, motivo in omitidos:
            print(f"  fila {excel_row_num} | rfc original: {rfc_raw!r} | {motivo}")


if __name__ == "__main__":
    main()
