"""Paso 1 de la importación de vales históricos: genera el Excel de
revisión con la propuesta para cada vale del año indicado (ver
apps.gastos.importacion). No toca la base de datos."""
import datetime
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.gastos import importacion
from apps.gastos.models import CentroCosto, ConceptoGasto, Vehiculo

EXCEL_POLIZAS = Path(settings.BASE_DIR).parent / "datos" / "GASTOS-POLIZAS CP LAURA 2024-05.xlsx"


class Command(BaseCommand):
    help = "Genera el Excel de revisión de los vales de gastos de un año, a partir del Excel de pólizas."

    def add_arguments(self, parser):
        parser.add_argument("--excel", default=str(EXCEL_POLIZAS), help="Excel de pólizas de origen.")
        parser.add_argument("--anio", type=int, default=2026)
        parser.add_argument("--salida", help="Ruta del Excel de revisión (por defecto, junto al de origen).")
        parser.add_argument(
            "--fecha-corte",
            help="Fecha a partir de la cual una fecha de vale se considera mal capturada (AAAA-MM-DD). "
            "Por defecto, la fecha de modificación del Excel de origen.",
        )

    def handle(self, *args, excel, anio, salida, fecha_corte, **options):
        origen = Path(excel)
        if not origen.exists():
            raise CommandError(f"No encuentro {origen}")
        if fecha_corte:
            try:
                corte = datetime.date.fromisoformat(fecha_corte)
            except ValueError as error:
                raise CommandError("--fecha-corte debe tener el formato AAAA-MM-DD.") from error
        else:
            corte = datetime.date.fromtimestamp(origen.stat().st_mtime)
        destino = Path(salida) if salida else origen.with_name(f"REVISION GASTOS {anio}.xlsx")

        conceptos = list(ConceptoGasto.objects.filter(is_active=True).select_related("grupo"))
        centros = list(CentroCosto.objects.filter(is_active=True).exclude(codigo=None).order_by("codigo"))
        vehiculos = list(Vehiculo.objects.filter(is_active=True).order_by("nombre"))

        self.stdout.write(f"Leyendo {origen.name}...")
        vales = importacion.leer_polizas(origen)
        propuestas = importacion.proponer(
            vales,
            anio=anio,
            fecha_corte=corte,
            conceptos_validos={c.nombre for c in conceptos},
            centros_validos={c.codigo for c in centros},
            vehiculos_validos={v.nombre for v in vehiculos},
            conceptos_personales={c.nombre for c in conceptos if c.grupo.exclusivo_personal},
            centros_personales={c.codigo for c in centros if c.tipo == CentroCosto.Tipo.PERSONAL},
        )
        importacion.escribir_revision(
            destino,
            propuestas,
            centros=[(c.codigo, c.nombre) for c in centros],
            conceptos=[(c.grupo.nombre, c.nombre) for c in conceptos],
            vehiculos=[v.nombre for v in vehiculos],
        )

        por_accion = Counter(p.accion for p in propuestas)
        total = sum(p.vale.importe for p in propuestas if p.accion == importacion.IMPORTAR)
        self.stdout.write(self.style.SUCCESS(f"Archivo de revisión: {destino}"))
        self.stdout.write(f"Vales de {anio}: {len(propuestas)} (fecha de corte {corte:%d/%m/%Y})")
        for accion in importacion.ACCIONES:
            self.stdout.write(f"  {accion}: {por_accion.get(accion, 0)}")
        self.stdout.write(f"  Importe propuesto para importar: ${total:,.2f}")
