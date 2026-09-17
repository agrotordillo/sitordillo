"""Consolida clientes duplicados: mismo RFC del sistema anterior capturado
más de una vez, que por eso terminó como más de un Cliente en esta base
(el import original -import_legacy_clientes- creaba un Cliente por cada
fila del archivo legado, sin detectar que el RFC ya se había importado;
esa fuga ya se corrigió ahí, pero no retroactivamente).

datos/asociado.sql trae 170 RFC (normalizados sin espacios/guiones) que se
repiten. La normalización laxa por sí sola es una trampa: agrupa también
basura de captura que por casualidad cae en el mismo texto tras limpiarla
("X1X1X1X1X1X1X", "XXXXXXXXXXXXX", una variante mal tecleada del genérico
XAXX010101000...) y hasta un RFC real pero compartido a propósito entre
entidades distintas (ej. GET710101FW1 usado para "GOBIERNO DEL ESTADO" Y
varias escuelas públicas no relacionadas entre sí). Ninguno de esos casos es
"la misma persona capturada dos veces": son decenas de clientes distintos.
Por eso solo se considera duplicado real un grupo que:
  1. Tiene formato de RFC válido (RFC_PATTERN) una vez limpio de espacios.
  2. Tiene 3 Cliente o menos ya cruzados en esta base -un RFC "compartido" a
     propósito entre muchas cuentas reales siempre se ve en grupos grandes;
     una persona capturada dos o tres veces por error, no-.
El cruce hacia esos Cliente usa el mismo criterio que
backfill_lista_precio_clientes (nota "RFC del sistema anterior" en
observaciones, o nombre_fiscal único).

Aun así, un RFC igual con nombres sin relación entre sí sigue pasando estos
dos filtros (ej. RFC=SEP210905778 en "SECRETARIA DE EDUCACION PUBLICA" y en
"CENTRO DE BACHILLERATO TECNOLOGICO AGROPECUARIO NO. 199": mismo RFC oficial
usado por dependencias distintas, no el mismo cliente). Por eso, antes de
borrar cualquier candidato se exige que su nombre comparta al menos una
palabra significativa con el nombre que se va a conservar; si no comparte
ninguna, ese candidato se dejó fuera del borrado automático y se reporta
para revisión manual. También se evita conservar un nombre que es basura de
captura (solo repite un carácter, no tiene vocales, o es el propio RFC)
cuando hay otro candidato en el grupo con un nombre de verdad.

De cada grupo se intenta borrar todo menos el que se conserva (el que trae
la nota de RFC, o si ninguno la trae, el primer nombre que no sea basura).
Cliente.ventas/cotizaciones usan on_delete=PROTECT, así que si algún
duplicado ya tiene una venta o cotización real, Django rechaza el borrado
solo para ese registro y se reporta para revisión manual -nunca se
fuerza."""
import re
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ProtectedError

from apps.clientes.management.commands.import_legacy_clientes import (
    RFC_GENERICOS, RFC_PATTERN, norm_rfc_laxo,
)
from apps.clientes.models import Cliente
from apps.products.management.commands.import_legacy_productos import parse_sql_rows

DATA_DIR = Path(settings.BASE_DIR).parent / "datos"
COLUMNAS = [
    "id", "tipo", "rfc", "nombre_fiscal", "nombre_comercial", "nombre_contacto",
    "descuento", "credito_autorizado", "limite_credito", "dias_credito",
    "observaciones", "lista_precio", "sat_cfdi_3_3_c_regimenfiscal", "id_ruta",
    "incluir_en_estado_de_resultados", "figura_tipo", "figura_licencia", "id_grupo",
]

RFC_NOTA_RE = re.compile(r"RFC del sistema anterior:\s*([A-ZÑ&0-9]+)")

STOPWORDS = {
    "DE", "DEL", "LA", "LOS", "LAS", "Y", "EN", "EL",
    "SA", "CV", "RL", "SC", "AC", "AR", "SRL", "S", "A", "C", "V", "R", "L",
}


def norm(valor):
    return (valor or "").strip().upper()


def tokens_significativos(nombre):
    return {p for p in re.findall(r"[A-ZÑ]+", norm(nombre)) if len(p) >= 3 and p not in STOPWORDS}


def es_nombre_basura(nombre, rfc):
    n = norm(nombre)
    if not n or n == rfc:
        return True
    sin_espacios = n.replace(" ", "")
    if len(set(sin_espacios)) <= 2:
        return True
    letras = re.sub(r"[^A-ZÑ]", "", n)
    if not letras or sum(1 for ch in letras if ch in "AEIOUÑ") / len(letras) < 0.15:
        return True
    return False


class Command(BaseCommand):
    help = "Borra clientes duplicados (mismo RFC del sistema anterior) que no tengan ventas ni cotizaciones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Borra de verdad; sin esta bandera solo reporta (dry-run, comportamiento por default).",
        )

    def handle(self, *args, **options):
        aplicar = options["apply"]

        path = DATA_DIR / "asociado.sql"
        if not path.exists():
            raise CommandError(f"No encuentro {path}")

        filas = parse_sql_rows(path)
        clientes_legado = [dict(zip(COLUMNAS, row)) for row in filas if row[1] == "CLIENTE"]

        TAM_MAX_GRUPO = 3  # ver docstring: un RFC compartido a propósito entre
        # muchas cuentas reales siempre da grupos grandes; una persona
        # capturada por error dos o tres veces, no.

        grupos_legado = defaultdict(list)
        for r in clientes_legado:
            rfc = norm_rfc_laxo(r["rfc"])
            if rfc and rfc not in RFC_GENERICOS and RFC_PATTERN.match(rfc):
                grupos_legado[rfc].append(r)
        grupos_legado = {k: v for k, v in grupos_legado.items() if len(v) > 1}
        self.stdout.write(f"RFC con formato válido repetidos en asociado.sql: {len(grupos_legado)}")

        clientes = list(Cliente.objects.all().only("id", "nombre", "observaciones"))
        por_rfc_nota = defaultdict(list)
        por_nombre = defaultdict(list)
        for c in clientes:
            m = RFC_NOTA_RE.search(c.observaciones or "")
            if m:
                por_rfc_nota[m.group(1)].append(c.id)
            por_nombre[norm(c.nombre)].append(c.id)

        casos, revision_manual = [], []
        sin_duplicado_real = grupos_grandes_omitidos = 0
        for rfc, filas_legado in grupos_legado.items():
            ids = set(por_rfc_nota.get(rfc, []))
            for r in filas_legado:
                candidatos = por_nombre.get(norm(r["nombre_fiscal"]), [])
                if len(candidatos) == 1:
                    ids.add(candidatos[0])
            if len(ids) < 2:
                sin_duplicado_real += 1
                continue
            if len(ids) > TAM_MAX_GRUPO:
                # RFC probablemente compartido/genérico, no un duplicado de
                # captura: no se toca, queda para revisión manual.
                grupos_grandes_omitidos += 1
                continue

            ids = sorted(ids)
            nombres = {c.id: c.nombre for c in clientes if c.id in ids}
            con_nota = [c for c in ids if c in por_rfc_nota.get(rfc, [])]
            no_basura = [c for c in ids if not es_nombre_basura(nombres[c], rfc)]
            con_nota_normal = [c for c in con_nota if c in no_basura]
            # Prioridad para elegir cuál se conserva: el que trae la nota de
            # RFC Y además tiene un nombre real (no basura de captura, como
            # cuando alguien tecleó el propio RFC en el campo de nombre);
            # si ninguno cumple ambas, cualquier nombre real gana sobre la
            # nota; si todos son basura, la nota; si nada de eso, id más bajo.
            if con_nota_normal:
                conservar = con_nota_normal[0]
            elif no_basura:
                conservar = no_basura[0]
            elif con_nota:
                conservar = con_nota[0]
            else:
                conservar = ids[0]
            tokens_conservar = tokens_significativos(nombres[conservar])

            a_borrar, a_revisar = [], []
            for cid in ids:
                if cid == conservar:
                    continue
                comparten = tokens_conservar & tokens_significativos(nombres[cid])
                if es_nombre_basura(nombres[cid], rfc) or comparten:
                    a_borrar.append(cid)
                else:
                    # Nombre real pero sin ninguna palabra en común con el que
                    # se conserva (ej. RFC oficial reusado entre entidades
                    # distintas): no se adivina, se deja para revisión manual.
                    a_revisar.append(cid)

            if a_borrar:
                casos.append((rfc, conservar, a_borrar, nombres))
            if a_revisar:
                revision_manual.append((rfc, conservar, a_revisar, nombres))

        self.stdout.write(
            f"Grupos con duplicado real a consolidar: {len(casos)} · "
            f"sin duplicado real en esta base: {sin_duplicado_real} · "
            f"omitidos por grupo grande (probable RFC compartido, revisar a mano): {grupos_grandes_omitidos}"
        )
        self.stdout.write("Detalle de lo que se conserva/borra:")
        for rfc, conservar, a_borrar, nombres in casos:
            self.stdout.write(
                f"  - RFC={rfc} conserva id={conservar} ({nombres.get(conservar)!r}) "
                f"borra={[(cid, nombres.get(cid)) for cid in a_borrar]}"
            )
        if revision_manual:
            self.stdout.write(self.style.WARNING(
                f"{len(revision_manual)} candidatos con el mismo RFC pero nombre sin relación "
                "(no se tocan, revisar a mano):"
            ))
            for rfc, conservar, a_revisar, nombres in revision_manual:
                self.stdout.write(
                    f"  - RFC={rfc} se conservaría id={conservar} ({nombres.get(conservar)!r}) "
                    f"pero no se borra={[(cid, nombres.get(cid)) for cid in a_revisar]}"
                )

        if not aplicar:
            total = sum(len(a_borrar) for _, _, a_borrar, _ in casos)
            self.stdout.write(self.style.WARNING(
                f"Dry-run: se borrarían {total} clientes duplicados. Corre con --apply para aplicar."
            ))
            return

        borrados, protegidos = 0, []
        for rfc, conservar, a_borrar, _ in casos:
            for cid in a_borrar:
                try:
                    Cliente.objects.get(pk=cid).delete()
                    borrados += 1
                except ProtectedError:
                    protegidos.append((rfc, conservar, cid))
                except Cliente.DoesNotExist:
                    continue

        self.stdout.write(self.style.SUCCESS(f"Listo. {borrados} clientes duplicados borrados."))
        if protegidos:
            self.stdout.write(self.style.WARNING(
                f"{len(protegidos)} no se pudieron borrar por tener ventas/cotizaciones (revisión manual):"
            ))
            for rfc, conservar, cid in protegidos:
                self.stdout.write(f"  - RFC={rfc} conservado={conservar} con historial (no borrado)={cid}")
