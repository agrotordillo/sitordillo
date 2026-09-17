"""Backfill de Cliente.lista_precio usando datos/asociado.sql (export fresco
de la tabla `asociado` del sistema legado, que trae clientes y proveedores
juntos). El import original (import_legacy_clientes, desde CLIENTES.xlsx) ya
había intentado fijar esta lista de precio, pero ese xlsx es una foto vieja:
el dump de asociado.sql es más reciente y trae precios preferentes
capturados o corregidos después en el sistema anterior.

Cliente no guarda ninguna clave del sistema legado para enlazar de vuelta
con `asociado.id`, así que el cruce se hace por lo que sí sobrevivió del
import original:
  1. RFC: cuando el RFC legado tenía formato válido, el import original lo
     dejó como nota de texto en observaciones ("RFC del sistema anterior:
     XXX"). Si ese RFC es único en asociado.sql, es el cruce más confiable.
  2. nombre_fiscal: si el nombre (tal cual quedó en Cliente.nombre) es único
     tanto en asociado.sql como entre los Cliente actuales, se cruza por
     nombre exacto (mayúsculas, espacios recortados).
Los que no se pueden enlazar de forma inequívoca (nombre repetido y sin RFC
que lo distinga) se listan para revisión manual: no se adivina."""
import re
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.clientes.management.commands.import_legacy_clientes import LISTA_PRECIO_POR_INDICE
from apps.clientes.models import Cliente
from apps.products.management.commands.import_legacy_productos import parse_sql_rows
from apps.products.models import ListaPrecio

DATA_DIR = Path(settings.BASE_DIR).parent / "datos"
COLUMNAS = [
    "id", "tipo", "rfc", "nombre_fiscal", "nombre_comercial", "nombre_contacto",
    "descuento", "credito_autorizado", "limite_credito", "dias_credito",
    "observaciones", "lista_precio", "sat_cfdi_3_3_c_regimenfiscal", "id_ruta",
    "incluir_en_estado_de_resultados", "figura_tipo", "figura_licencia", "id_grupo",
]

RFC_NOTA_RE = re.compile(r"RFC del sistema anterior:\s*([A-ZÑ&0-9]+)")


def norm(valor):
    return (valor or "").strip().upper()


class Command(BaseCommand):
    help = "Actualiza Cliente.lista_precio con el dato de datos/asociado.sql (tabla legada `asociado`)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Escribe los cambios; sin esta bandera solo reporta (dry-run, comportamiento por default).",
        )

    def handle(self, *args, **options):
        aplicar = options["apply"]

        path = DATA_DIR / "asociado.sql"
        if not path.exists():
            raise CommandError(f"No encuentro {path}")

        filas = parse_sql_rows(path)
        clientes_legado = [dict(zip(COLUMNAS, row)) for row in filas if row[1] == "CLIENTE"]
        self.stdout.write(f"Filas CLIENTE leídas de asociado.sql: {len(clientes_legado)}")

        lista_precio_obj = {
            indice: ListaPrecio.objects.filter(nombre=nombre).first()
            for indice, nombre in LISTA_PRECIO_POR_INDICE.items()
        }
        faltantes = [n for i, n in LISTA_PRECIO_POR_INDICE.items() if lista_precio_obj[i] is None]
        if faltantes:
            raise CommandError(f"No encuentro estas ListaPrecio en la base de datos: {faltantes}")

        # Índices de asociado.sql por RFC y por nombre_fiscal, descartando
        # los que se repiten (cruce ambiguo, no se usan).
        por_rfc, por_nombre = {}, {}
        rfc_repetido, nombre_repetido = set(), set()
        for r in clientes_legado:
            rfc = norm(r["rfc"])
            if rfc:
                if rfc in por_rfc:
                    rfc_repetido.add(rfc)
                else:
                    por_rfc[rfc] = r
            nombre = norm(r["nombre_fiscal"])
            if nombre:
                if nombre in por_nombre:
                    nombre_repetido.add(nombre)
                else:
                    por_nombre[nombre] = r
        for rfc in rfc_repetido:
            por_rfc.pop(rfc, None)
        for nombre in nombre_repetido:
            por_nombre.pop(nombre, None)

        clientes = list(Cliente.objects.all().only("id", "nombre", "observaciones", "lista_precio_id"))
        nombre_actual_count = Counter(norm(c.nombre) for c in clientes)

        stats = Counter()
        a_actualizar = []
        sin_match = []
        for c in clientes:
            match = None
            m = RFC_NOTA_RE.search(c.observaciones or "")
            if m:
                match = por_rfc.get(m.group(1))
                if match:
                    stats["cruce_por_rfc"] += 1
            if match is None:
                nombre = norm(c.nombre)
                if nombre_actual_count[nombre] == 1:
                    match = por_nombre.get(nombre)
                    if match:
                        stats["cruce_por_nombre"] += 1
            if match is None:
                sin_match.append(c)
                stats["sin_cruce"] += 1
                continue

            indice = match["lista_precio"]
            indice_int = int(indice) if indice is not None else None
            nueva_lista = lista_precio_obj.get(indice_int)
            if nueva_lista is None:
                stats["indice_sin_catalogo"] += 1
                continue
            if c.lista_precio_id == nueva_lista.id:
                stats["ya_correcto"] += 1
                continue
            c.lista_precio_id = nueva_lista.id
            a_actualizar.append(c)
            stats["a_actualizar"] += 1

        self.stdout.write(
            f"Clientes en BD: {len(clientes)} | cruce por RFC: {stats['cruce_por_rfc']} | "
            f"cruce por nombre único: {stats['cruce_por_nombre']} | sin cruce: {stats['sin_cruce']}"
        )
        self.stdout.write(
            f"De los cruzados: ya correcto={stats['ya_correcto']} · a actualizar={stats['a_actualizar']} · "
            f"índice de lista sin catálogo (5/6/7/8/9)={stats['indice_sin_catalogo']}"
        )
        if sin_match:
            self.stdout.write(self.style.WARNING(f"Sin cruce ({len(sin_match)}), primeros 20:"))
            for c in sin_match[:20]:
                self.stdout.write(f"  - id={c.id} nombre={c.nombre!r} lista_precio_actual={c.lista_precio_id}")

        if not aplicar:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada. Corre con --apply para aplicar."))
            return

        Cliente.objects.bulk_update(a_actualizar, ["lista_precio"], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Listo. {len(a_actualizar)} clientes actualizados."))
