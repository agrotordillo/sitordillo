"""Paso 2 de la importación de vales históricos: importa las filas
marcadas IMPORTAR del Excel de revisión ya revisado (ver
apps.gastos.importacion). Sin --aplicar solo valida y no guarda nada; con
--aplicar, si alguna fila tiene error no se importa ninguna."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.gastos import importacion


class Command(BaseCommand):
    help = "Valida e importa el Excel de revisión de vales de gastos (usa --aplicar para guardar)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Excel de revisión generado por generar_revision_gastos.")
        parser.add_argument("--aplicar", action="store_true", help="Guarda los gastos (sin esto solo valida).")

    def handle(self, *args, archivo, aplicar, **options):
        ruta = Path(archivo)
        if not ruta.exists():
            raise CommandError(f"No encuentro {ruta}")
        try:
            filas = importacion.leer_revision(ruta)
        except ValueError as error:
            raise CommandError(str(error)) from error

        resultado = importacion.importar_revision(filas, aplicar=aplicar)

        for accion, cantidad in sorted(resultado.por_accion.items()):
            self.stdout.write(f"  {accion}: {cantidad}")
        if resultado.por_accion.get(importacion.REVISAR):
            self.stdout.write(self.style.WARNING(
                f"{resultado.por_accion[importacion.REVISAR]} filas siguen en REVISAR y no se importan."
            ))
        if resultado.ya_importadas:
            self.stdout.write(f"{resultado.ya_importadas} filas ya se habían importado antes; se saltan.")
        if resultado.errores:
            for error in resultado.errores:
                self.stdout.write(self.style.ERROR(error))
            raise CommandError(
                f"{len(resultado.errores)} filas con error: corrígelas en el archivo. No se importó nada."
            )

        total = sum(g.importe for g in resultado.gastos)
        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"Importados {resultado.creados} gastos por ${total:,.2f}."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Sin errores: se importarían {len(resultado.gastos)} gastos por ${total:,.2f}. "
                "Corre de nuevo con --aplicar para guardarlos."
            ))
