"""Importa clientes desde datos/CLIENTES.xlsx (export del sistema legado).

Decisiones tomadas (el usuario delegó el criterio para no bloquear la
importación en más rondas de preguntas):
  - RFC: NO se asigna al campo Cliente.rfc directamente. Cliente.clean()
    exige rfc+nombre_fiscal+regimen_fiscal+uso_cfdi+codigo_postal todos
    juntos o ninguno, y el archivo no trae uso_cfdi ni código postal —
    fijar solo el RFC dejaría a ese cliente sin poder guardarse desde el
    formulario web (ni para editar algo no fiscal) hasta completar los 4
    datos. En vez de eso, cuando el RFC tiene formato válido (RFC_PATTERN),
    no es uno de los genéricos de "público en general" (XAXX010101000 y
    variantes mal tecleadas) y no se repite (el primer cliente que lo trae
    se lo queda), se guarda como nota de texto en observaciones para
    completarlo a mano cuando se le vaya a facturar. El 64% de los RFC del
    archivo son basura de captura (".", "XXXXXXXXX", etc.), así que la
    mayoría de los clientes no traen ninguna nota de RFC.
  - régimen fiscal / uso de CFDI / código postal / tipo_persona NO se
    importan, por la misma razón de arriba: se completan a mano junto con
    el RFC cuando se le vaya a facturar a ese cliente.
  - tiene_credito = bandera "credito_autorizado" (SI/NO), tal cual. Si dice
    NO, el límite y los días de crédito capturados se descartan (quedan en
    0) aunque el archivo traiga algo distinto (1,889 casos así) — se confía
    en la bandera, no en el número.
  - lista_precio: el archivo trae un índice 0-9 que corresponde al mismo
    orden ya usado para las listas de precio de producto. Solo 0-4
    (Público/Medio mayoreo/Mayoreo/Sub distribuidor/Promoción) tienen
    sentido como "lista por defecto" de un cliente; el resto de los
    índices son específicos de sucursal y se dejan sin asignar.
  - nombre_contacto y nombre_comercial no tienen campo propio en Cliente:
    cuando difieren de nombre_fiscal (y no son basura obvia como "." o ","),
    se anexan como nota en observaciones para no perder el dato.
  - id_ruta, id_grupo, figura_tipo, figura_licencia,
    incluir_en_estado_de_resultados: sin destino en el modelo actual, no se
    importan.
"""
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.clientes.models import Cliente
from apps.products.models import ListaPrecio

RFC_PATTERN = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
RFC_GENERICOS = {"XAXX010101000", "XEXX010101000", "XAX101010000"}
JUNK_TEXTO = {"", ".", ",", "-", ".-", "..", ",,", "NULL", "N/A"}

LIMITE_CREDITO_MAX = Decimal("9999999999.99")  # Cliente.limite_credito: max_digits=12, decimal_places=2

LISTA_PRECIO_POR_INDICE = {
    0: "PUBLICO",
    1: "MEDIO MAYOREO",
    2: "MAYOREO",
    3: "SUB DISTRIBUIDOR",
    4: "PROMOCION",
}

DATA_DIR = Path(settings.BASE_DIR).parent / "datos"
COLUMNAS = [
    "id", "tipo", "rfc", "nombre_fiscal", "nombre_comercial", "nombre_contacto",
    "descuento", "credito_autorizado", "limite_credito", "dias_credito",
    "observaciones", "lista_precio", "sat_cfdi_3_3_c_regimenfiscal", "id_ruta",
    "incluir_en_estado_de_resultados", "figura_tipo", "figura_licencia", "id_grupo",
]


def limpio(valor):
    return (str(valor).strip() if valor is not None else "")


def to_decimal(valor, default=Decimal("0.00")):
    if valor is None or valor == "":
        return default
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return default


class Command(BaseCommand):
    help = "Importa clientes desde datos/CLIENTES.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Permite correr aunque ya existan clientes.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if not dry_run and Cliente.objects.exists() and not force:
            raise CommandError(
                "Ya existen clientes en la base de datos. Usa --force si de verdad quieres reimportar."
            )

        path = DATA_DIR / "CLIENTES.xlsx"
        if not path.exists():
            raise CommandError(f"No encuentro {path}")

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb["Hoja1"]
        filas = list(ws.iter_rows(min_row=2, values_only=True))
        self.stdout.write(f"Filas leídas: {len(filas)}")

        lista_precio_obj = {
            indice: ListaPrecio.objects.filter(nombre=nombre).first()
            for indice, nombre in LISTA_PRECIO_POR_INDICE.items()
        }
        faltantes = [n for i, n in LISTA_PRECIO_POR_INDICE.items() if lista_precio_obj[i] is None]
        if faltantes:
            raise CommandError(f"No encuentro estas ListaPrecio en la base de datos: {faltantes}")

        stats = {
            "clientes": 0, "omitidos": 0, "sin_rfc": 0, "credito_bandera_gano": 0,
            "limite_credito_saneado": 0, "errores": [],
        }
        rfcs_usados = set()

        try:
            with transaction.atomic():
                for row in filas:
                    r = dict(zip(COLUMNAS, row))
                    try:
                        with transaction.atomic():
                            self._crear_cliente(r, lista_precio_obj, rfcs_usados, stats)
                    except Exception as exc:  # noqa: BLE001
                        stats["omitidos"] += 1
                        stats["errores"].append(f"id={r.get('id')} nombre={r.get('nombre_fiscal')!r}: {exc}")
                        continue
                    stats["clientes"] += 1
                    if stats["clientes"] % 1000 == 0:
                        self.stdout.write(f"  ... {stats['clientes']} clientes importados")
                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada, se revirtió la transacción."))

        self.stdout.write(self.style.SUCCESS(
            f"Listo. Clientes={stats['clientes']} (omitidos por error: {stats['omitidos']}) "
            f"sin RFC={stats['sin_rfc']} bandera NO gano sobre numero capturado={stats['credito_bandera_gano']} "
            f"limite_credito saneado (absurdo)={stats['limite_credito_saneado']}"
        ))
        if stats["errores"]:
            self.stdout.write(self.style.WARNING(f"Errores ({len(stats['errores'])}), primeros 20:"))
            for e in stats["errores"][:20]:
                self.stdout.write(f"  - {e}")

    def _crear_cliente(self, r, lista_precio_obj, rfcs_usados, stats):
        nombre_fiscal = limpio(r["nombre_fiscal"])
        if not nombre_fiscal:
            raise ValueError("nombre_fiscal vacío")

        # No se asigna Cliente.rfc/nombre_fiscal directamente: Cliente.clean()
        # exige rfc+nombre_fiscal+regimen_fiscal+uso_cfdi+codigo_postal todos
        # juntos o ninguno (validación "todo o nada" para poder facturar). El
        # archivo no trae uso_cfdi ni código postal, así que fijar solo el
        # RFC dejaría a ese cliente sin poder guardarse desde el formulario
        # web (hasta editar cualquier campo no fiscal) mientras no se
        # completen los 4 datos. El RFC válido se preserva como nota de
        # texto para completarlo a mano cuando se le vaya a facturar.
        rfc_raw = limpio(r["rfc"]).upper()
        rfc_valido = bool(
            RFC_PATTERN.match(rfc_raw)
            and rfc_raw not in RFC_GENERICOS
            and rfc_raw not in rfcs_usados
        )
        if rfc_valido:
            rfcs_usados.add(rfc_raw)
        else:
            stats["sin_rfc"] += 1

        notas = []
        observaciones_legado = limpio(r["observaciones"])
        if observaciones_legado:
            notas.append(observaciones_legado)
        if rfc_valido:
            notas.append(f"RFC del sistema anterior: {rfc_raw}")
        nombre_contacto = limpio(r["nombre_contacto"])
        if nombre_contacto and nombre_contacto.upper() not in JUNK_TEXTO and nombre_contacto.upper() != nombre_fiscal.upper():
            notas.append(f"Contacto: {nombre_contacto}")
        nombre_comercial = limpio(r["nombre_comercial"])
        if nombre_comercial and nombre_comercial.upper() not in JUNK_TEXTO and nombre_comercial.upper() != nombre_fiscal.upper():
            notas.append(f"Nombre comercial: {nombre_comercial}")
        observaciones = " · ".join(notas)

        limite_credito = to_decimal(r["limite_credito"])
        if limite_credito > LIMITE_CREDITO_MAX:
            # Valores absurdos de captura (ej. $50,000,000,000,000 o
            # 555555555555): ni cabrían en el campo, ni son un límite real.
            limite_credito = Decimal("0.00")
            stats["limite_credito_saneado"] += 1
        dias_credito = int(to_decimal(r["dias_credito"]))
        credito_bandera = limpio(r["credito_autorizado"]).upper() == "SI"
        # Se confía en la bandera, no en los números: si dice NO, el límite y
        # los días capturados se descartan (quedan en 0), aunque el archivo
        # traiga algo distinto (1,889 casos así).
        tiene_credito = credito_bandera
        if not tiene_credito:
            if limite_credito > 0 or dias_credito > 0:
                stats["credito_bandera_gano"] += 1
            limite_credito = Decimal("0.00")
            dias_credito = 0

        descuento = to_decimal(r["descuento"])
        if descuento < 0 or descuento > 100:
            descuento = Decimal("0.00")

        lista_precio = None
        indice = r["lista_precio"]
        if isinstance(indice, (int, float)):
            lista_precio = lista_precio_obj.get(int(indice))

        cliente = Cliente(
            nombre=nombre_fiscal,
            lista_precio=lista_precio,
            tiene_credito=tiene_credito,
            limite_credito=limite_credito,
            dias_credito=dias_credito,
            descuento=descuento,
            observaciones=observaciones,
        )
        cliente.save()


class _DryRunRollback(Exception):
    pass
