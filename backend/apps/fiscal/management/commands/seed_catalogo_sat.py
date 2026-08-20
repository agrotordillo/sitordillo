"""Siembra el catálogo oficial del SAT (CFDI 4.0) para ClaveProdServSAT y
ClaveUnidadSAT, a partir de los dumps SQL (dialecto SQLite) publicados por el
proyecto open-source phpcfdi/resources-sat-catalogs
(https://github.com/phpcfdi/resources-sat-catalogs), tablas
`cfdi_40_productos_servicios` y `cfdi_40_claves_unidades`.

Los archivos se descargan una sola vez a datos/sat/*.sql (no van al repo,
son ~7.4 MB) y este comando los parsea e inserta en bloque.
"""
import random
import string
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.fiscal.models import ClaveProdServSAT, ClaveUnidadSAT

DATA_DIR = Path(settings.BASE_DIR).parent / "datos" / "sat"
ALPHANUM = string.ascii_uppercase + string.digits


def parse_sqlite_values(line):
    start = line.index("VALUES(") + len("VALUES(")
    end = line.rstrip().rstrip(";").rfind(")")
    body = line[start:end]
    values = []
    buf = []
    in_str = False
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if in_str:
            if c == "'":
                if i + 1 < n and body[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
                i += 1
                continue
            buf.append(c)
            i += 1
        else:
            if c == "'":
                in_str = True
                i += 1
            elif c == ",":
                values.append("".join(buf))
                buf = []
                i += 1
            else:
                buf.append(c)
                i += 1
    values.append("".join(buf))
    return values


def parse_sqlite_dump(path):
    rows = []
    with open(path, encoding="utf8") as f:
        for line in f:
            if not line.startswith("INSERT INTO"):
                continue
            rows.append(parse_sqlite_values(line))
    return rows


def random_folio(prefix, used):
    while True:
        candidate = f"{prefix}-{''.join(random.choices(ALPHANUM, k=8))}"
        if candidate not in used:
            used.add(candidate)
            return candidate


class Command(BaseCommand):
    help = "Siembra ClaveProdServSAT y ClaveUnidadSAT desde datos/sat/*.sql (catálogo oficial CFDI 4.0)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        prod_serv_path = DATA_DIR / "cfdi_40_productos_servicios.sql"
        unidades_path = DATA_DIR / "cfdi_40_claves_unidades.sql"
        for p in (prod_serv_path, unidades_path):
            if not p.exists():
                raise CommandError(f"No encuentro {p}")

        prod_serv_rows = parse_sqlite_dump(prod_serv_path)
        unidades_rows = parse_sqlite_dump(unidades_path)
        self.stdout.write(f"Leídas: productos/servicios={len(prod_serv_rows)} unidades={len(unidades_rows)}")

        existing_ps = set(ClaveProdServSAT.objects.values_list("clave", flat=True))
        existing_un = set(ClaveUnidadSAT.objects.values_list("clave", flat=True))
        used_folios = set(ClaveProdServSAT.objects.values_list("folio", flat=True)) | set(
            ClaveUnidadSAT.objects.values_list("folio", flat=True)
        )

        nuevos_ps = []
        for row in prod_serv_rows:
            clave, texto = row[0], row[1]
            if not clave or clave in existing_ps:
                continue
            existing_ps.add(clave)
            nuevos_ps.append(ClaveProdServSAT(
                uuid=uuid.uuid4(),
                folio=random_folio("CPS", used_folios),
                slug=slugify(clave) or str(uuid.uuid4()),
                clave=clave,
                descripcion=texto or clave,
            ))

        nuevos_un = []
        for row in unidades_rows:
            clave, texto, _descripcion, _notas, _desde, _hasta, simbolo = row[:7]
            if not clave or clave in existing_un:
                continue
            existing_un.add(clave)
            nuevos_un.append(ClaveUnidadSAT(
                uuid=uuid.uuid4(),
                folio=random_folio("CUS", used_folios),
                slug=slugify(clave) or str(uuid.uuid4()),
                clave=clave,
                nombre=texto or clave,
                simbolo=(simbolo or "")[:20],
            ))

        self.stdout.write(f"Nuevos a insertar: productos/servicios={len(nuevos_ps)} unidades={len(nuevos_un)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
            return

        with transaction.atomic():
            ClaveProdServSAT.objects.bulk_create(nuevos_ps, batch_size=2000)
            ClaveUnidadSAT.objects.bulk_create(nuevos_un, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(
            f"Listo. ClaveProdServSAT total={ClaveProdServSAT.objects.count()} "
            f"ClaveUnidadSAT total={ClaveUnidadSAT.objects.count()}"
        ))
