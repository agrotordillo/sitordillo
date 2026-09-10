"""Importa proveedores desde datos/proveedores.xlsx (export del sistema legado).

Reemplaza al script de una sola vez scripts/import_proveedores.py.

Columnas esperadas en la hoja "Hoja1":
    tipo, rfc, nombre_fiscal, nombre_comercial, nombre_contacto, descuento,
    credito_autorizado, limite_credito, dias_credito, observaciones,
    lista_precio (ignorada, sin campo equivalente en el modelo),
    sat_cfdi_3_3_c_regimenfiscal (clave SAT de RegimenFiscal)

Decisiones tomadas (ver script original):
  - Solo se procesan las filas cuyo campo `tipo` es "PROVEEDOR".
  - tipo_persona se infiere por la longitud del RFC normalizado
    (13 = persona física, 12 = persona moral).
  - Cada fila se valida con Proveedor.full_clean(); las filas que no pasan
    validación (RFC inválido, régimen fiscal incompatible con el tipo de
    persona, límite/días de crédito sin crédito autorizado, RFC duplicado,
    etc.) se omiten y se listan al final para revisión manual.
  - Caso especial del régimen 612: en el archivo fuente el régimen SAT 612
    (Personas Físicas con Actividades Empresariales y Profesionales) se usó
    como valor por defecto para casi todos los proveedores, incluidos varios
    con RFC de persona moral (12 caracteres), para quienes ese régimen no es
    válido. En esos casos se sustituye el régimen por 601 (General de Ley
    Personas Morales) y se reporta como ajuste, en vez de omitir la fila.
"""
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.validators import RFC_PATTERN
from apps.fiscal.models import RegimenFiscal
from apps.proveedores.models import Proveedor

DATA_DIR = Path(settings.BASE_DIR).parent / "datos"
SHEET_NAME = "Hoja1"
PLACEHOLDER_VALUES = {"", ".", "NULL"}

COLUMNAS = [
    "tipo", "rfc", "nombre_fiscal", "nombre_comercial", "nombre_contacto",
    "descuento", "credito_autorizado", "limite_credito", "dias_credito",
    "observaciones", "lista_precio", "sat_cfdi_3_3_c_regimenfiscal",
]


def normalize_rfc(raw):
    if raw is None:
        return ""
    return re.sub(r"[\s\-]", "", str(raw)).upper()


def clean_text(raw):
    if raw is None:
        return ""
    value = str(raw).strip()
    return "" if value.upper() in PLACEHOLDER_VALUES else value


def to_decimal(valor, default=Decimal("0.00")):
    if valor is None or valor == "":
        return default
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return default


class Command(BaseCommand):
    help = "Importa proveedores desde datos/proveedores.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Permite correr aunque ya existan proveedores.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if not dry_run and Proveedor.objects.exists() and not force:
            raise CommandError(
                "Ya existen proveedores en la base de datos. Usa --force si de verdad quieres reimportar."
            )

        path = DATA_DIR / "proveedores.xlsx"
        if not path.exists():
            raise CommandError(f"No encuentro {path}")

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[SHEET_NAME]
        filas = list(ws.iter_rows(min_row=2, values_only=True))
        self.stdout.write(f"Filas leídas: {len(filas)}")

        regimenes = {r.clave: r for r in RegimenFiscal.objects.all()}
        regimen_601 = regimenes.get("601")

        stats = {
            "proveedores": 0, "omitidos": 0, "ignorados_no_proveedor": 0,
            "regimen_ajustado_601": 0, "ajustes": [], "errores": [],
        }
        rfcs_en_archivo = set()

        try:
            with transaction.atomic():
                for excel_row_num, row in enumerate(filas, start=2):
                    r = dict(zip(COLUMNAS, row))
                    try:
                        with transaction.atomic():
                            resultado = self._crear_proveedor(
                                excel_row_num, r, regimenes, regimen_601, rfcs_en_archivo, stats
                            )
                    except Exception as exc:  # noqa: BLE001
                        stats["omitidos"] += 1
                        stats["errores"].append(
                            f"fila {excel_row_num} rfc={r.get('rfc')!r}: {exc}"
                        )
                        continue
                    if resultado == "creado":
                        stats["proveedores"] += 1
                        if stats["proveedores"] % 500 == 0:
                            self.stdout.write(f"  ... {stats['proveedores']} proveedores importados")
                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada, se revirtió la transacción."))

        self.stdout.write(self.style.SUCCESS(
            f"Listo. Proveedores={stats['proveedores']} "
            f"(omitidos por error/validación: {stats['omitidos']}, "
            f"filas ignoradas por no ser PROVEEDOR: {stats['ignorados_no_proveedor']}) "
            f"régimen ajustado a 601={stats['regimen_ajustado_601']}"
        ))
        if stats["ajustes"]:
            self.stdout.write(self.style.WARNING(f"Detalle de filas con régimen ajustado ({len(stats['ajustes'])}):"))
            for linea in stats["ajustes"][:20]:
                self.stdout.write(f"  - {linea}")
        if stats["errores"]:
            self.stdout.write(self.style.WARNING(f"Errores ({len(stats['errores'])}), primeros 20:"))
            for e in stats["errores"][:20]:
                self.stdout.write(f"  - {e}")

    def _crear_proveedor(self, excel_row_num, r, regimenes, regimen_601, rfcs_en_archivo, stats):
        if clean_text(r["tipo"]).upper() != "PROVEEDOR":
            stats["ignorados_no_proveedor"] += 1
            return "ignorado"

        rfc = normalize_rfc(r["rfc"])
        if len(rfc) not in (12, 13) or not RFC_PATTERN.match(rfc):
            raise ValueError("RFC con formato inválido")

        if rfc in rfcs_en_archivo:
            raise ValueError("RFC duplicado dentro del archivo")

        if Proveedor.objects.filter(rfc=rfc).exists():
            raise ValueError("Ya existe un proveedor con este RFC")

        sat_cfdi = r["sat_cfdi_3_3_c_regimenfiscal"]
        if sat_cfdi is None or clean_text(sat_cfdi) == "":
            raise ValueError("Sin clave de régimen fiscal SAT")

        try:
            clave_regimen = str(int(sat_cfdi))
        except (TypeError, ValueError):
            clave_regimen = clean_text(sat_cfdi)
        regimen = regimenes.get(clave_regimen)
        if regimen is None:
            raise ValueError(f"Clave de régimen fiscal SAT {sat_cfdi!r} no existe en el catálogo")

        tipo_persona = (
            Proveedor.TipoPersona.FISICA if len(rfc) == 13 else Proveedor.TipoPersona.MORAL
        )

        if tipo_persona == Proveedor.TipoPersona.MORAL and not regimen.aplica_moral:
            if regimen_601 is None:
                raise ValueError(
                    "RFC de persona moral con régimen que no aplica y no existe el régimen 601 en el catálogo"
                )
            stats["ajustes"].append(
                f"fila {excel_row_num} | rfc {rfc} | régimen {regimen.clave} -> 601 "
                f"(persona moral, régimen original no aplica)"
            )
            stats["regimen_ajustado_601"] += 1
            regimen = regimen_601

        descuento = to_decimal(r["descuento"])
        if descuento < 0 or descuento > 100:
            descuento = Decimal("0.00")

        tiene_credito = clean_text(r["credito_autorizado"]).upper() == "SI"
        limite_credito = to_decimal(r["limite_credito"]) if tiene_credito else Decimal("0.00")
        dias_credito = int(to_decimal(r["dias_credito"])) if tiene_credito else 0

        proveedor = Proveedor(
            tipo_persona=tipo_persona,
            rfc=rfc,
            nombre_fiscal=clean_text(r["nombre_fiscal"]),
            nombre_comercial=clean_text(r["nombre_comercial"]),
            regimen_fiscal=regimen,
            tiene_credito=tiene_credito,
            limite_credito=limite_credito,
            dias_credito=dias_credito,
            descuento=descuento,
            contacto_nombre=clean_text(r["nombre_contacto"]),
            observaciones=clean_text(r["observaciones"]),
        )

        try:
            proveedor.full_clean()
        except ValidationError as exc:
            raise ValueError("; ".join(f"{k}: {', '.join(v)}" for k, v in exc.message_dict.items())) from exc

        proveedor.save()
        rfcs_en_archivo.add(rfc)
        return "creado"


class _DryRunRollback(Exception):
    pass
