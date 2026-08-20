"""Importa productos, marcas, categorías, líneas y unidades de medida desde
los dumps de MySQL/phpMyAdmin del sistema viejo (datos/*.sql) hacia el modelo
Producto actual, incluyendo las listas de precio (ListaPrecio/ProductoPrecio).

Decisiones tomadas junto con el usuario (ver conversación de la fase de
migración de datos de apps.products):
  - codigo_barras del legado es basura ('-', '.', ',', '0') en el 100% de los
    casos con valor: se ignora, todos los productos quedan sin código de
    barras.
  - El único registro con impuesto_iva anómalo (1600% en vez de 16%) se
    normaliza dividiendo entre 100.
  - tipo ARTICULO y COMPUESTO (no hay datos de componentes exportados para
    COMPUESTO) se mapean a PRODUCTO; SERVICIO se mapea a SERVICIO.
  - Marca: 3 pares de nombres duplicados (mismo nombre, distinto id legado)
    se fusionan en un solo registro.
  - Línea vive como catálogo/FK independiente en Producto (no anidada bajo
    Categoría: en los datos reales el 31% de las categorías aparece bajo más
    de una línea).
  - Clase se descarta por completo (catch-all sin significado de negocio
    consistente).
  - id_punto_entrega se ignora (100% vacío en los datos reales).
  - Las 10 columnas de precio/utilidad se mapean así:
      1 PUBLICO (general), 2 MEDIO MAYOREO (general), 3 MAYOREO (general),
      4 SUB DISTRIBUIDOR (general), 5 PROMOCION (general),
      6 PUBLICO override IQUINUAPA, 7 PUBLICO override HUIMANGUILLO,
      8 PUBLICO override BODEGA SUR (CEDIS), 9 MAYOREO override BODEGA SUR,
      10 (N/A) se descarta.
  - clave_prod_serv_sat / clave_unidad_sat se dejan sin asignar: el catálogo
    oficial del SAT (fiscal.ClaveProdServSAT / ClaveUnidadSAT) todavía está
    vacío en este sistema: no se crean claves "stub" para no ensuciar ese
    catálogo cuando se siembre con los datos oficiales en una fase aparte.
"""
import ast
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.models import (
    Almacen,
    Categoria,
    Linea,
    ListaPrecio,
    Marca,
    Producto,
    ProductoPrecio,
    UnidadMedida,
)

DATA_DIR = Path(settings.BASE_DIR).parent / "datos"
TWO_PLACES = Decimal("0.01")

PRODUCTO_COLS = [
    "id", "codigo", "nombre", "tipo", "estado", "descripcion", "costeo", "costo",
    "utilidad_1", "utilidad_2", "utilidad_3", "utilidad_4", "utilidad_5",
    "utilidad_6", "utilidad_7", "utilidad_8", "utilidad_9", "utilidad_10",
    "exento", "impuesto_iva", "impuesto_ieps",
    "precio_sin_impuesto_1", "precio_sin_impuesto_2", "precio_sin_impuesto_3",
    "precio_sin_impuesto_4", "precio_sin_impuesto_5", "precio_sin_impuesto_6",
    "precio_sin_impuesto_7", "precio_sin_impuesto_8", "precio_sin_impuesto_9",
    "precio_sin_impuesto_10",
    "codigo_barras", "id_unidad_medida", "imagen", "id_linea", "id_marca",
    "id_categoria", "control",
    "importe_utilidad_1", "importe_utilidad_2", "importe_utilidad_3",
    "importe_utilidad_4", "importe_utilidad_5", "importe_utilidad_6",
    "importe_utilidad_7", "importe_utilidad_8", "importe_utilidad_9", "importe_utilidad_10",
    "importe_impuesto_iva_1", "importe_impuesto_iva_2", "importe_impuesto_iva_3",
    "importe_impuesto_iva_4", "importe_impuesto_iva_5", "importe_impuesto_iva_6",
    "importe_impuesto_iva_7", "importe_impuesto_iva_8", "importe_impuesto_iva_9",
    "importe_impuesto_iva_10",
    "importe_impuesto_ieps_1", "importe_impuesto_ieps_2", "importe_impuesto_ieps_3",
    "importe_impuesto_ieps_4", "importe_impuesto_ieps_5", "importe_impuesto_ieps_6",
    "importe_impuesto_ieps_7", "importe_impuesto_ieps_8", "importe_impuesto_ieps_9",
    "importe_impuesto_ieps_10",
    "precio_con_impuesto_1", "precio_con_impuesto_2", "precio_con_impuesto_3",
    "precio_con_impuesto_4", "precio_con_impuesto_5", "precio_con_impuesto_6",
    "precio_con_impuesto_7", "precio_con_impuesto_8", "precio_con_impuesto_9",
    "precio_con_impuesto_10",
    "existencia_minima", "existencia_maxima", "control_auxiliar",
    "id_unidad_medida_auxiliar", "factor_unidad_medida_auxiliar",
    "sat_cfdi_3_3_c_claveprodserv", "peso", "dias_reserva", "id_clase",
    "fecha_modificacion", "codigo_proveedor", "id_punto_entrega",
]

# (posicion, nombre_lista, nombre_almacen_override_o_None)
PRECIO_POSICIONES = [
    (1, "PUBLICO", None),
    (2, "MEDIO MAYOREO", None),
    (3, "MAYOREO", None),
    (4, "SUB DISTRIBUIDOR", None),
    (5, "PROMOCION", None),
    (6, "PUBLICO", "IQUINUAPA"),
    (7, "PUBLICO", "HUIMANGUILLO"),
    (8, "PUBLICO", "BODEGA SUR"),
    (9, "MAYOREO", "BODEGA SUR"),
]
LISTA_NOMBRES = ["PUBLICO", "MEDIO MAYOREO", "MAYOREO", "SUB DISTRIBUIDOR", "PROMOCION"]

MARCA_MERGE = {115: 114, 203: 140, 180: 173}

TIPO_MAP = {
    "ARTICULO": Producto.TipoProducto.PRODUCTO,
    "COMPUESTO": Producto.TipoProducto.PRODUCTO,
    "SERVICIO": Producto.TipoProducto.SERVICIO,
}

BARCODE_JUNK = {"-", ".", ",", "0", ""}


def parse_sql_rows(path):
    rows = []
    with open(path, encoding="utf8") as f:
        for line in f:
            s = line.strip()
            if not s.startswith("("):
                continue
            if s.endswith(","):
                s = s[:-1]
            elif s.endswith(");"):
                s = s[:-1]
            else:
                continue
            py = re.sub(r"\bNULL\b", "None", s)
            try:
                rows.append(ast.literal_eval(py))
            except (SyntaxError, ValueError):
                continue
    return rows


def to_decimal(value, places=TWO_PLACES):
    if value is None:
        return None
    return Decimal(str(value)).quantize(places, rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = "Importa productos del sistema legado (datos/*.sql) al modelo Producto actual."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo reporta.")
        parser.add_argument("--force", action="store_true", help="Permite correr aunque ya existan productos.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if not dry_run and Producto.objects.exists() and not force:
            raise CommandError(
                "Ya existen productos en la base de datos. Usa --force si de verdad "
                "quieres volver a importar (puede duplicar datos)."
            )

        for name in ("marca", "categoria", "linea", "unidad_medida", "producto"):
            path = DATA_DIR / f"{name}.sql"
            if not path.exists():
                raise CommandError(f"No encuentro {path}")

        marca_rows = parse_sql_rows(DATA_DIR / "marca.sql")
        categoria_rows = parse_sql_rows(DATA_DIR / "categoria.sql")
        linea_rows = parse_sql_rows(DATA_DIR / "linea.sql")
        unidad_rows = parse_sql_rows(DATA_DIR / "unidad_medida.sql")
        producto_rows = parse_sql_rows(DATA_DIR / "producto.sql")

        self.stdout.write(
            f"Filas leídas: marca={len(marca_rows)} categoria={len(categoria_rows)} "
            f"linea={len(linea_rows)} unidad_medida={len(unidad_rows)} producto={len(producto_rows)}"
        )

        try:
            with transaction.atomic():
                stats = self._import_all(marca_rows, categoria_rows, linea_rows, unidad_rows, producto_rows)
                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada, se revirtió la transacción."))

        self.stdout.write(self.style.SUCCESS(
            f"Listo. Marcas={stats['marcas']} Categorias={stats['categorias']} "
            f"Lineas={stats['lineas']} UnidadesMedida={stats['unidades']} "
            f"Almacenes creados={stats['almacenes_creados']} "
            f"ListasPrecio={stats['listas_precio']} "
            f"Productos={stats['productos']} (omitidos por error: {stats['productos_omitidos']}) "
            f"ProductoPrecio={stats['producto_precios']} "
            f"Nombres desambiguados={stats['nombres_desambiguados']}"
        ))
        if stats["errores"]:
            self.stdout.write(self.style.WARNING(f"Errores ({len(stats['errores'])}), primeros 20:"))
            for e in stats["errores"][:20]:
                self.stdout.write(f"  - {e}")

    def _import_all(self, marca_rows, categoria_rows, linea_rows, unidad_rows, producto_rows):
        stats = {
            "marcas": 0, "categorias": 0, "lineas": 0, "unidades": 0,
            "almacenes_creados": 0, "listas_precio": 0,
            "productos": 0, "productos_omitidos": 0, "producto_precios": 0,
            "nombres_desambiguados": 0, "errores": [],
        }

        # --- Marca (con fusión de duplicados) ---
        marca_by_legacy_id = {}
        marca_by_nombre = {}
        for row in marca_rows:
            legacy_id, _codigo, nombre = row[0], row[1], row[2].strip()
            canonical_id = MARCA_MERGE.get(legacy_id, legacy_id)
            if canonical_id != legacy_id:
                continue  # se resuelve cuando procesemos el id canónico
            obj = marca_by_nombre.get(nombre.lower())
            if obj is None:
                obj = Marca.objects.create(nombre=nombre)
                marca_by_nombre[nombre.lower()] = obj
                stats["marcas"] += 1
            marca_by_legacy_id[legacy_id] = obj
        for loser_id, winner_id in MARCA_MERGE.items():
            marca_by_legacy_id[loser_id] = marca_by_legacy_id[winner_id]

        # --- Categoria ---
        categoria_by_legacy_id = {}
        for legacy_id, _codigo, nombre in categoria_rows:
            nombre = nombre.strip()
            obj, created = Categoria.objects.get_or_create(nombre__iexact=nombre, defaults={"nombre": nombre})
            if created:
                stats["categorias"] += 1
            categoria_by_legacy_id[legacy_id] = obj

        # --- Linea ---
        linea_by_legacy_id = {}
        for row in linea_rows:
            legacy_id, _codigo, nombre = row[0], row[1], row[2].strip()
            obj, created = Linea.objects.get_or_create(nombre__iexact=nombre, defaults={"nombre": nombre})
            if created:
                stats["lineas"] += 1
            linea_by_legacy_id[legacy_id] = obj

        # --- UnidadMedida ---
        unidad_by_legacy_id = {}
        for row in unidad_rows:
            legacy_id, codigo, nombre = row[0], row[1].strip(), row[2].strip()
            obj = UnidadMedida.objects.filter(nombre__iexact=nombre).first()
            if obj is None:
                obj, created = UnidadMedida.objects.get_or_create(
                    abreviatura=codigo, defaults={"nombre": nombre}
                )
                if created:
                    stats["unidades"] += 1
            unidad_by_legacy_id[legacy_id] = obj

        # --- Almacenes para overrides de sucursal ---
        iquinuapa, created = Almacen.objects.get_or_create(
            nombre__iexact="IQUINUAPA", defaults={"nombre": "IQUINUAPA", "tipo": Almacen.Tipo.SUCURSAL}
        )
        if created:
            stats["almacenes_creados"] += 1
        huimanguillo, created = Almacen.objects.get_or_create(
            nombre__iexact="HUIMANGUILLO", defaults={"nombre": "HUIMANGUILLO", "tipo": Almacen.Tipo.SUCURSAL}
        )
        if created:
            stats["almacenes_creados"] += 1
        bodega_sur = Almacen.objects.filter(nombre__iexact="BODEGA SUR").first()
        if bodega_sur is None:
            raise CommandError("No encuentro el almacén 'BODEGA SUR' (tipo CEDIS); revisa el catálogo Almacen.")

        almacen_por_nombre = {
            "IQUINUAPA": iquinuapa,
            "HUIMANGUILLO": huimanguillo,
            "BODEGA SUR": bodega_sur,
        }

        # --- ListaPrecio ---
        lista_by_nombre = {}
        for i, nombre in enumerate(LISTA_NOMBRES, start=1):
            obj, created = ListaPrecio.objects.get_or_create(nombre=nombre, defaults={"orden": i})
            if created:
                stats["listas_precio"] += 1
            lista_by_nombre[nombre] = obj

        # --- Productos ---
        nombres_usados = {}
        for row in producto_rows:
            r = dict(zip(PRODUCTO_COLS, row))
            try:
                # savepoint por producto: si uno falla, solo se revierte ese
                # producto y sus precios, no toda la importación.
                with transaction.atomic():
                    producto, precios_creados = self._crear_producto(
                        r, marca_by_legacy_id, categoria_by_legacy_id, linea_by_legacy_id,
                        unidad_by_legacy_id, lista_by_nombre, almacen_por_nombre, nombres_usados, stats,
                    )
            except Exception as exc:  # noqa: BLE001 - queremos seguir con los demás productos
                stats["productos_omitidos"] += 1
                stats["errores"].append(f"id={r['id']} codigo={r['codigo']!r}: {exc}")
                continue
            stats["productos"] += 1
            stats["producto_precios"] += precios_creados
            if stats["productos"] % 1000 == 0:
                self.stdout.write(f"  ... {stats['productos']} productos importados")

        return stats

    def _crear_producto(
        self, r, marca_by_legacy_id, categoria_by_legacy_id, linea_by_legacy_id,
        unidad_by_legacy_id, lista_by_nombre, almacen_por_nombre, nombres_usados, stats,
    ):
        sku = r["codigo"].strip()
        nombre = r["nombre"].strip()
        key = nombre.lower()
        if key in nombres_usados:
            nombre = f"{nombre} ({sku})"
            stats["nombres_desambiguados"] += 1
        nombres_usados[key] = True

        tipo = TIPO_MAP.get(r["tipo"], Producto.TipoProducto.PRODUCTO)
        is_active = r["estado"] == "ACTIVO"

        exento = r["exento"] == "SI"
        impuesto_iva = Decimal(str(r["impuesto_iva"])) if r["impuesto_iva"] is not None else Decimal("0")
        if impuesto_iva > 100:
            impuesto_iva = impuesto_iva / Decimal("100")
        if exento:
            tipo_iva = Producto.TipoIVA.EXENTO
            tasa_iva = Decimal("0.00")
        else:
            # Gravado admite tasa 0% ("tasa cero", Art. 2-A LIVA): agropecuarios,
            # veterinarios, etc. No se fuerza a 16% cuando el legado trae 0.
            tipo_iva = Producto.TipoIVA.GRAVADO
            tasa_iva = to_decimal(impuesto_iva)

        impuesto_ieps = Decimal(str(r["impuesto_ieps"])) if r["impuesto_ieps"] is not None else Decimal("0")
        aplica_ieps = impuesto_ieps > 0
        tasa_ieps = to_decimal(impuesto_ieps, Decimal("0.0001")) if aplica_ieps else None

        codigo_barras = (r["codigo_barras"] or "").strip()
        if codigo_barras.lower() in BARCODE_JUNK:
            codigo_barras = None

        marca = marca_by_legacy_id.get(r["id_marca"])
        categoria = categoria_by_legacy_id.get(r["id_categoria"])
        linea = linea_by_legacy_id.get(r["id_linea"])
        unidad_medida = unidad_by_legacy_id.get(r["id_unidad_medida"])

        precio_costo = to_decimal(r["costo"]) or Decimal("0.00")
        stock_minimo = Decimal(r["existencia_minima"] or 0)
        stock_maximo = Decimal(r["existencia_maxima"] or 0)
        if stock_maximo < stock_minimo:
            stock_maximo = stock_minimo

        peso = to_decimal(r["peso"], Decimal("0.001")) if r["peso"] else None
        dias_reserva = int(r["dias_reserva"]) if r["dias_reserva"] else 0
        codigo_proveedor = (r["codigo_proveedor"] or "").strip()

        costeo_legado = (r["costeo"] or "").strip().lower()
        costeo = costeo_legado if costeo_legado in Producto.Costeo.values else Producto.Costeo.MANUAL

        producto = Producto(
            nombre=nombre,
            sku=sku,
            codigo_barras=codigo_barras,
            marca=marca,
            categoria=categoria,
            subcategoria=None,
            linea=linea,
            tipo=tipo,
            unidad_medida=unidad_medida,
            tipo_iva=tipo_iva,
            tasa_iva=tasa_iva,
            aplica_ieps=aplica_ieps,
            tasa_ieps=tasa_ieps,
            descripcion=(r["descripcion"] or "").strip(),
            costeo=costeo,
            precio_costo=precio_costo,
            precio_venta=Decimal("0.00"),
            stock_minimo=stock_minimo,
            stock_maximo=stock_maximo,
            peso=peso,
            dias_reserva=dias_reserva,
            codigo_proveedor=codigo_proveedor,
        )
        producto.is_active = is_active
        producto.save()

        # Precio de venta "público" por defecto, para no dejar precio_venta en 0
        # mientras el resto del sistema migra a ProductoPrecio.
        precio_publico = to_decimal(r["precio_con_impuesto_1"])
        if precio_publico:
            producto.precio_venta = precio_publico
            producto.save(update_fields=["precio_venta"])

        precios_creados = 0
        for posicion, lista_nombre, almacen_nombre in PRECIO_POSICIONES:
            precio_val = to_decimal(r[f"precio_con_impuesto_{posicion}"])
            if not precio_val:
                continue
            utilidad_val = to_decimal(r[f"utilidad_{posicion}"], Decimal("0.0001"))
            if utilidad_val is not None and abs(utilidad_val) >= Decimal("1000"):
                # ProductoPrecio.utilidad_pct es solo referencia (max_digits=7);
                # un valor legado fuera de rango no debe tumbar la importación.
                utilidad_val = None
            ProductoPrecio.objects.create(
                producto=producto,
                lista_precio=lista_by_nombre[lista_nombre],
                almacen=almacen_por_nombre.get(almacen_nombre) if almacen_nombre else None,
                utilidad_pct=utilidad_val,
                precio_con_impuesto=precio_val,
            )
            precios_creados += 1

        return producto, precios_creados


class _DryRunRollback(Exception):
    pass
