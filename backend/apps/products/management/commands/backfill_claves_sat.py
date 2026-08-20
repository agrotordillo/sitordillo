"""Backfill de Producto.clave_prod_serv_sat / clave_unidad_sat usando el
código SAT que traía datos/producto.sql y datos/unidad_medida.sql, ahora que
el catálogo oficial (fiscal.ClaveProdServSAT / ClaveUnidadSAT) ya está
sembrado (ver seed_catalogo_sat). Se corre después de import_legacy_productos.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.fiscal.models import ClaveProdServSAT, ClaveUnidadSAT
from apps.products.management.commands.import_legacy_productos import (
    DATA_DIR, PRODUCTO_COLS, parse_sql_rows,
)
from apps.products.models import Producto


class Command(BaseCommand):
    help = "Vincula clave_prod_serv_sat / clave_unidad_sat en Producto usando el catálogo oficial ya sembrado."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        producto_path = DATA_DIR / "producto.sql"
        unidad_path = DATA_DIR / "unidad_medida.sql"
        for p in (producto_path, unidad_path):
            if not p.exists():
                raise CommandError(f"No encuentro {p}")

        unidad_rows = parse_sql_rows(unidad_path)
        # id_unidad_medida legado -> codigo SAT de esa unidad
        unidad_sat_code = {row[0]: (row[3] or "").strip() for row in unidad_rows}

        prodserv_by_clave = {c.clave: c.id for c in ClaveProdServSAT.objects.all().only("id", "clave")}
        unidad_by_clave = {c.clave: c.id for c in ClaveUnidadSAT.objects.all().only("id", "clave")}

        producto_rows = parse_sql_rows(producto_path)
        sku_to_ids = {}
        for row in producto_rows:
            r = dict(zip(PRODUCTO_COLS, row))
            sku = r["codigo"].strip()
            prodserv_code = (r["sat_cfdi_3_3_c_claveprodserv"] or "").strip()
            unidad_code = unidad_sat_code.get(r["id_unidad_medida"], "")
            sku_to_ids[sku] = (
                prodserv_by_clave.get(prodserv_code),
                unidad_by_clave.get(unidad_code),
            )

        productos = list(Producto.objects.all().only("id", "sku"))
        actualizados = 0
        sin_prodserv = 0
        sin_unidad = 0
        for p in productos:
            ps_id, un_id = sku_to_ids.get(p.sku, (None, None))
            if ps_id is None:
                sin_prodserv += 1
            if un_id is None:
                sin_unidad += 1
            if ps_id or un_id:
                p.clave_prod_serv_sat_id = ps_id
                p.clave_unidad_sat_id = un_id
                actualizados += 1

        self.stdout.write(
            f"Productos a actualizar: {actualizados} de {len(productos)} "
            f"(sin clave prod/serv resuelta: {sin_prodserv}, sin clave unidad resuelta: {sin_unidad})"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
            return

        Producto.objects.bulk_update(
            [p for p in productos if p.clave_prod_serv_sat_id or p.clave_unidad_sat_id],
            ["clave_prod_serv_sat", "clave_unidad_sat"],
            batch_size=1000,
        )
        self.stdout.write(self.style.SUCCESS(f"Listo. {actualizados} productos actualizados."))
