"""Exporta de una copia de scv_web (el sistema anterior, MariaDB) los archivos
TSV que leen import_legacy_compras e import_legacy_ventas (ver
apps.core.scv_web).

Usa el cliente de línea de comandos de MariaDB (no hace falta un driver de
MySQL en el entorno de Django) en modo --batch --raw: sin encabezado, un
renglón por línea, separado por tabuladores. Por eso cada campo de texto se
limpia en la consulta (sin tabuladores ni saltos de línea).

Qué se exporta, desde --desde (por defecto 2025-01-01):
  - ventas: notas de venta y remisiones no canceladas. Las FACTURAS no: todas
    agrupan notas (documento_notas) y repiten sus renglones.
  - devoluciones: notas de devolución activas.
  - compras: gastos activos de la cuenta 2999 "MATERIALES PARA VENTA
    (ALMACEN)", que es donde scv_web registra la entrada por compra.
  - asociados: los clientes y proveedores de esos documentos.
  - vendedores: los usuarios de scv_web a los que se atribuye cada venta, para
    las comisiones (ver scv_web.VendedoresLegado).
  - existencias: lo que hay de cada producto en cada almacén al momento de la
    copia, para el inventario inicial (import_legacy_existencias). No depende
    de --desde: es el saldo de toda la historia.
  - catalogos/*.sql: volcado actual de producto, marca, categoría, línea,
    clase y unidad (con mariadb-dump), para dar de alta los productos que se
    crearon en scv_web después del volcado original.
"""
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.scv_web import DATA_DIR

CUENTA_COMPRAS = "2999"
# Producto y sus catálogos, para dar de alta los productos nuevos de scv_web
# (import_legacy_productos --solo-nuevos).
TABLAS_CATALOGO = ["marca", "categoria", "linea", "clase", "unidad_medida", "producto"]


def t(campo):
    """Campo de texto sin NULL, tabuladores ni saltos de línea."""
    return f"REPLACE(REPLACE(REPLACE(IFNULL({campo}, ''), '\\t', ' '), '\\n', ' '), '\\r', ' ')"


VENTAS_WHERE = (
    "d.fecha >= @desde AND d.tipo IN ('NOTA_VENTA', 'NOTA_REMISION') AND d.estado <> 'CANCELADO'"
)
DEVOLUCIONES_WHERE = "d.fecha >= @desde AND d.tipo = 'NOTA_DEVOLUCION' AND d.estado = 'ACTIVO'"
COMPRAS_JOIN = "gasto g JOIN cuenta cu ON cu.id = g.id_cuenta"
COMPRAS_WHERE = f"cu.codigo = '{CUENTA_COMPRAS}' AND g.estado = 'ACTIVO' AND g.fecha >= @desde"

# Nombre del archivo -> consulta. El orden de las columnas es el que esperan
# los comandos de importación; los detalles van ordenados por su encabezado.
CONSULTAS = {
    "ventas": f"""
        SELECT d.id, d.tipo, {t('d.folio')}, d.fecha, d.id_cliente, IFNULL(a.codigo, ''), d.estado_pago,
               IFNULL(d.efectivo_recibido, 0), d.total, IFNULL(d.id_vendedor, 0)
        FROM documento d
        LEFT JOIN movimiento_almacen m ON m.id = d.id_movimiento_almacen
        LEFT JOIN almacen a ON a.id = m.id_almacen
        WHERE {VENTAS_WHERE} ORDER BY d.id""",
    "ventas_productos": f"""
        SELECT p.id, p.id_documento, {t('pr.codigo')}, p.cantidad, IFNULL(p.costo, 0), p.precio, p.importe,
               p.total, IFNULL(p.tipo_precio, 0)
        FROM documento d JOIN documento_productos p ON p.id_documento = d.id
        LEFT JOIN producto pr ON pr.id = p.id_producto
        WHERE {VENTAS_WHERE} ORDER BY p.id_documento, p.id""",
    "ventas_pagos": f"""
        SELECT dmp.id, dmp.id_documento, IFNULL(mp.sat_cfdi_3_3_c_formapago, ''), dmp.importe,
               {t('dmp.referencia_pago')}
        FROM documento d JOIN documento_metodos_pago dmp ON dmp.id_documento = d.id
        LEFT JOIN metodo_pago mp ON mp.id = dmp.id_metodo_pago
        WHERE {VENTAS_WHERE} ORDER BY dmp.id_documento, dmp.id""",
    "devoluciones": f"""
        SELECT d.id, {t('d.folio')}, d.fecha, IFNULL(d.id_documento_origen, 0), {t('LEFT(d.observaciones, 500)')}
        FROM documento d WHERE {DEVOLUCIONES_WHERE} ORDER BY d.id""",
    "devoluciones_productos": f"""
        SELECT p.id, p.id_documento, {t('pr.codigo')}, p.cantidad
        FROM documento d JOIN documento_productos p ON p.id_documento = d.id
        LEFT JOIN producto pr ON pr.id = p.id_producto
        WHERE {DEVOLUCIONES_WHERE} ORDER BY p.id_documento, p.id""",
    "compras": f"""
        SELECT g.id, g.fecha, g.id_proveedor, IFNULL(a.codigo, ''), {t('g.referencia')}, g.estado_pago,
               IFNULL(g.medio_pago, ''), IFNULL(mp.sat_cfdi_3_3_c_formapago, ''), g.es_fiscal,
               g.importe_impuesto_iva, g.importe_impuesto_ieps, g.importe_retencion_iva,
               g.importe_retencion_isr, g.total, {t('LEFT(g.observacion, 500)')}
        FROM {COMPRAS_JOIN}
        LEFT JOIN almacen a ON a.id = g.id_almacen_recibe
        LEFT JOIN metodo_pago mp ON mp.id = g.id_metodo_pago
        WHERE {COMPRAS_WHERE} ORDER BY g.id""",
    "compras_productos": f"""
        SELECT d.id, d.id_gasto, {t('pr.codigo')}, d.cantidad, d.valor_unitario, d.importe
        FROM {COMPRAS_JOIN}
        JOIN gasto_detalles d ON d.id_gasto = g.id
        LEFT JOIN producto pr ON pr.id = d.id_producto
        WHERE {COMPRAS_WHERE} ORDER BY d.id_gasto, d.id""",
    "asociados": f"""
        SELECT a.id, a.tipo, {t('a.rfc')}, {t('a.nombre_fiscal')}, {t('a.nombre_comercial')},
               {t('a.nombre_contacto')}, a.descuento, a.credito_autorizado, a.limite_credito, a.dias_credito,
               {t('LEFT(a.observaciones, 500)')}, IFNULL(a.lista_precio, ''), IFNULL(a.sat_cfdi_3_3_c_regimenfiscal, '')
        FROM asociado a
        WHERE a.id IN (SELECT d.id_cliente FROM documento d WHERE {VENTAS_WHERE})
           OR a.id IN (SELECT g.id_proveedor FROM {COMPRAS_JOIN} WHERE {COMPRAS_WHERE})
        ORDER BY a.id""",
    # Existencia de cada producto en cada almacén al momento de la copia:
    # entradas - salidas de todos sus movimientos de almacén activos (ventas,
    # compras, traspasos, ajustes, conversiones dejan ahí su detalle). Así la
    # calcula el reporte de existencias de scv_web (grid_alm_existencias). El
    # costo es el actual del catálogo (producto.costo), el mismo de ese reporte.
    "existencias": f"""
        SELECT IFNULL(a.codigo, ''), {t('TRIM(p.codigo)')},
               SUM(IF(m.tipo = 'ENTRADA', md.cantidad, -md.cantidad)), IFNULL(p.costo, 0)
        FROM movimiento_almacen m
        JOIN movimiento_almacen_detalles md ON md.id_movimiento = m.id
        JOIN almacen a ON a.id = m.id_almacen
        JOIN producto p ON p.id = md.id_producto
        WHERE m.estado = 'ACTIVO'
        GROUP BY a.id, p.id
        HAVING ROUND(SUM(IF(m.tipo = 'ENTRADA', md.cantidad, -md.cantidad)), 3) <> 0
        ORDER BY a.codigo, p.codigo""",
    # documento.id_vendedor apunta a los usuarios de scv_web (slz_users).
    "vendedores": f"""
        SELECT u.id, {t('u.login')}, {t('u.name')}
        FROM slz_users u
        WHERE u.id IN (SELECT d.id_vendedor FROM documento d WHERE {VENTAS_WHERE})
        ORDER BY u.id""",
}


class Command(BaseCommand):
    help = "Exporta de una copia de scv_web (MariaDB) los TSV para importar ventas y compras históricas."

    def add_arguments(self, parser):
        parser.add_argument("--mariadb", required=True, help="Ruta al cliente mariadb.exe (o mysql.exe).")
        parser.add_argument(
            "--mariadb-dump", default="",
            help="Ruta a mariadb-dump.exe (o mysqldump.exe); por defecto, junto al cliente.",
        )
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--puerto", default="3307")
        parser.add_argument("--usuario", default="root")
        parser.add_argument("--password", default="")
        parser.add_argument("--base", default="scv_web")
        parser.add_argument("--desde", default="2025-01-01", help="Fecha inicial (AAAA-MM-DD) de ventas y compras.")
        parser.add_argument("--directorio", default=str(DATA_DIR))

    def handle(self, *args, **options):
        destino = Path(options["directorio"])
        destino.mkdir(parents=True, exist_ok=True)
        base = [
            options["mariadb"], f"--host={options['host']}", f"--port={options['puerto']}",
            f"--user={options['usuario']}", "--batch", "--raw", "--skip-column-names",
            "--default-character-set=utf8mb4", options["base"],
        ]
        if options["password"]:
            base.insert(4, f"--password={options['password']}")

        self._volcar_catalogos(options, destino / "catalogos")

        for nombre, consulta in CONSULTAS.items():
            sql = f"SET @desde = '{options['desde']}';\n{consulta};"
            ruta = destino / f"{nombre}.tsv"
            with open(ruta, "wb") as archivo:
                proceso = subprocess.run(base, input=sql.encode("utf8"), stdout=archivo, stderr=subprocess.PIPE)
            if proceso.returncode != 0:
                raise CommandError(f"{nombre}: {proceso.stderr.decode('utf8', 'replace').strip()}")
            with open(ruta, "rb") as archivo:
                filas = sum(1 for _ in archivo)
            self.stdout.write(f"  {ruta.name}: {filas:,} filas")
        self.stdout.write(self.style.SUCCESS(f"Listo, archivos en {destino}"))

    def _volcar_catalogos(self, options, destino):
        """Volcado actual de producto y sus catálogos, en el formato que lee
        import_legacy_productos (--solo-nuevos --directorio <destino>): un
        INSERT por renglón."""
        destino.mkdir(parents=True, exist_ok=True)
        cliente = Path(options["mariadb"])
        volcador = options["mariadb_dump"] or str(
            cliente.with_name("mariadb-dump.exe" if cliente.name.lower().startswith("mariadb") else "mysqldump.exe")
        )
        base = [
            volcador, f"--host={options['host']}", f"--port={options['puerto']}", f"--user={options['usuario']}",
            "--skip-extended-insert", "--no-create-info", "--compact", "--default-character-set=utf8mb4",
        ]
        if options["password"]:
            base.append(f"--password={options['password']}")
        for tabla in TABLAS_CATALOGO:
            ruta = destino / f"{tabla}.sql"
            with open(ruta, "wb") as archivo:
                proceso = subprocess.run([*base, options["base"], tabla], stdout=archivo, stderr=subprocess.PIPE)
            if proceso.returncode != 0:
                raise CommandError(f"{tabla}: {proceso.stderr.decode('utf8', 'replace').strip()}")
            with open(ruta, "rb") as archivo:
                filas = sum(1 for _ in archivo)
            self.stdout.write(f"  catalogos/{ruta.name}: {filas:,} filas")
