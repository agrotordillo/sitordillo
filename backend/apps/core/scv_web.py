"""Lectura y mapeo de los datos exportados de scv_web (el sistema anterior,
MariaDB) para importar su historial de ventas y compras.

El flujo es:
  1. `manage.py exportar_scv_web` saca de una copia de scv_web los archivos
     TSV de datos/scv_web/ (ver CONSULTAS en ese comando).
  2. `manage.py import_legacy_compras` e `import_legacy_ventas` los leen con
     este módulo; `import_legacy_existencias` carga el inventario inicial.

Decisiones tomadas con el usuario (evaluación del 2026-10-26):
  - El CEDIS de sitordillo es el antiguo 02 BODEGA SUR: sus compras van al
    CEDIS, pero sus ventas y su existencia a la sucursal BODEGA SUR (el CEDIS
    no vende).
  - Los almacenes que no existen se crean inactivos, solo para sostener el
    histórico: 07 CEDIS TORDILLO (como sucursal, porque solo puede haber un
    CEDIS) y los 10 móviles con ventas desde 2025 (tipo MOVIL). Se activan a
    mano el día que empiecen a operar aquí.
  - Clientes y proveedores se ligan por RFC y luego por nombre único; los que
    no existen se crean con las mismas reglas de import_legacy_clientes /
    import_legacy_proveedores.
"""
import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Max

from apps.clientes.models import Cliente
from apps.fiscal.models import FormaPago
from apps.products.models import Almacen, ListaPrecio, PRECIO_POSICIONES, Producto
from apps.proveedores.models import Proveedor

DATA_DIR = Path(settings.BASE_DIR).parent / "datos" / "scv_web"
ZONA = ZoneInfo(settings.TIME_ZONE)
NULO = "NULL"

# Código de almacén en scv_web -> nombre del almacén en sitordillo (búsqueda
# sin distinguir mayúsculas). El 02 es el único que se reparte distinto según
# el documento: ver almacen_de_venta / almacen_de_compra.
ALMACENES_EXISTENTES = {
    "01": "LERDO",
    "03": "TECOLUTILLA",
    "04": "ALDAMA",
    "05": "MERCADO",
    "06": "IQUINUAPA",
    "13": "HUIMANGUILLO",
}
SUCURSAL_VENTAS_BODEGA_SUR = "BODEGA SUR"
CODIGO_BODEGA_SUR = "02"
# (código, nombre, tipo) en el orden en que toman número de almacén.
ALMACENES_A_CREAR = [
    ("07", "CEDIS TORDILLO", Almacen.Tipo.SUCURSAL),
    ("M1", "MOVIL TRASPASOS SUR", Almacen.Tipo.MOVIL),
    ("M2", "MOVIL RUTA SUR", Almacen.Tipo.MOVIL),
    ("M3", "MOVIL CLIENTES SUR", Almacen.Tipo.MOVIL),
    ("M4", "MOVIL CLIENTES LERDO", Almacen.Tipo.MOVIL),
    ("M5", "MOVIL TRASPASOS LERDO", Almacen.Tipo.MOVIL),
    ("M6", "MOVIL RUTA LERDO", Almacen.Tipo.MOVIL),
    ("MT", "MOVIL TECOLUTILLA", Almacen.Tipo.MOVIL),
    ("MA", "MOVIL ALDAMA", Almacen.Tipo.MOVIL),
    ("MC", "MOVIL CEDIS TORDILLO", Almacen.Tipo.MOVIL),
    ("MI", "MOVIL IQUINUAPA", Almacen.Tipo.MOVIL),
]

DOS = Decimal("0.01")
CUATRO = Decimal("0.0001")


# --- Lectura -----------------------------------------------------------------

def leer_tsv(directorio, nombre, columnas):
    """Filas de `<directorio>/<nombre>.tsv` como dicts. El archivo sale del
    cliente de MariaDB en modo --batch --raw (ver exportar_scv_web): sin
    encabezado, separado por tabuladores, NULL como texto. Los campos de
    texto ya vienen sin tabuladores ni saltos de línea desde la consulta."""
    ruta = Path(directorio) / f"{nombre}.tsv"
    with open(ruta, encoding="utf8", newline="") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            linea = linea.rstrip("\r\n")
            if not linea:
                continue
            valores = linea.split("\t")
            if len(valores) != len(columnas):
                raise ValueError(
                    f"{ruta.name} línea {numero}: se esperaban {len(columnas)} columnas y hay {len(valores)}."
                )
            yield {col: (None if valor == NULO else valor) for col, valor in zip(columnas, valores)}


def agrupar_por(filas, clave):
    """Recorre `filas` (ya ordenadas por `clave`) entregando (valor, [filas])."""
    actual, grupo = None, []
    for fila in filas:
        valor = int(fila[clave])
        if grupo and valor != actual:
            yield actual, grupo
            grupo = []
        actual = valor
        grupo.append(fila)
    if grupo:
        yield actual, grupo


class Emparejador:
    """Avanza un iterador de grupos (agrupar_por) al mismo paso que una lista
    de encabezados ordenada por id: `de(id)` devuelve las filas de ese id, o
    [] si no tiene, descartando las de ids menores (huérfanas)."""

    def __init__(self, grupos):
        self._grupos = iter(grupos)
        self._pendiente = next(self._grupos, None)
        self.huerfanas = 0

    def de(self, id_encabezado):
        while self._pendiente is not None and self._pendiente[0] < id_encabezado:
            self.huerfanas += len(self._pendiente[1])
            self._pendiente = next(self._grupos, None)
        if self._pendiente is not None and self._pendiente[0] == id_encabezado:
            filas = self._pendiente[1]
            self._pendiente = next(self._grupos, None)
            return filas
        return []


def decimal(valor, lugares=DOS):
    if valor in (None, ""):
        return None
    try:
        return Decimal(valor).quantize(lugares)
    except InvalidOperation:
        return None


def fecha_hora(valor):
    """datetime de scv_web (hora local, sin zona) -> datetime con zona."""
    return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZONA)


def texto(valor, largo=None):
    valor = (valor or "").strip()
    return valor[:largo] if largo else valor


def normalizar_nombre(valor):
    return re.sub(r"\s+", " ", (valor or "").strip().upper())


def normalizar_rfc(valor):
    return re.sub(r"[^A-ZÑ&0-9]", "", (valor or "").upper())


# --- Catálogos ---------------------------------------------------------------

def productos_por_sku():
    return dict(Producto.objects.values_list("sku", "pk"))


def formas_pago_por_clave():
    return dict(FormaPago.objects.values_list("clave", "pk"))


def listas_por_tipo_precio():
    """tipo_precio de scv_web (posición 1..9 de la tabla de precios) -> pk de
    ListaPrecio; el 0 (precio libre) y el 10 no tienen lista."""
    listas = dict(ListaPrecio.objects.values_list("nombre", "pk"))
    return {str(posicion): listas.get(nombre) for posicion, nombre, _ in PRECIO_POSICIONES}


class Almacenes:
    """Resuelve el código de almacén de scv_web al Almacen de sitordillo,
    creando los que falten (inactivos) cuando `crear` es verdadero; en un
    dry-run solo los cuenta y devuelve None para esos códigos."""

    def __init__(self, crear):
        self.crear = crear
        self.creados = []
        por_nombre = {a.nombre.strip().upper(): a for a in Almacen.objects.all()}
        self.cedis = Almacen.objects.filter(tipo=Almacen.Tipo.CEDIS).first()
        if self.cedis is None:
            raise ValueError("No existe el almacén CEDIS en sitordillo.")
        self._por_codigo = {}
        faltantes = [n for n in [*ALMACENES_EXISTENTES.values(), SUCURSAL_VENTAS_BODEGA_SUR] if n not in por_nombre]
        if faltantes:
            raise ValueError(f"No existen en sitordillo estos almacenes: {', '.join(faltantes)}.")
        for codigo, nombre in ALMACENES_EXISTENTES.items():
            self._por_codigo[codigo] = por_nombre[nombre]
        self.sucursal_bodega_sur = por_nombre[SUCURSAL_VENTAS_BODEGA_SUR]

        siguiente = (Almacen.objects.aggregate(m=Max("numero"))["m"] or 0) + 1
        for codigo, nombre, tipo in ALMACENES_A_CREAR:
            almacen = por_nombre.get(nombre)
            if almacen is None:
                self.creados.append(f"{codigo} {nombre} ({tipo}, número {siguiente})")
                if crear:
                    almacen = Almacen(nombre=nombre, tipo=tipo, numero=siguiente)
                    almacen.is_active = False
                    almacen.save()
                siguiente += 1
            self._por_codigo[codigo] = almacen

    def de_venta(self, codigo):
        if codigo == CODIGO_BODEGA_SUR:
            return self.sucursal_bodega_sur
        return self._resolver(codigo)

    def de_compra(self, codigo):
        if codigo == CODIGO_BODEGA_SUR:
            return self.cedis
        return self._resolver(codigo)

    def de_existencia(self, codigo):
        """Dónde queda el inventario inicial (decisión del usuario,
        2026-10-27): la mercancía del 02 BODEGA SUR en la sucursal BODEGA SUR
        -que es la que vende-, y la de cada móvil en su móvil."""
        return self.de_venta(codigo)

    def _resolver(self, codigo):
        if codigo not in self._por_codigo:
            raise KeyError(codigo)
        return self._por_codigo[codigo]


# --- Clientes y proveedores --------------------------------------------------

# Mismas columnas que asociado.sql / CLIENTES.xlsx (ver import_legacy_clientes).
COLUMNAS_ASOCIADO = [
    "id", "tipo", "rfc", "nombre_fiscal", "nombre_comercial", "nombre_contacto",
    "descuento", "credito_autorizado", "limite_credito", "dias_credito",
    "observaciones", "lista_precio", "sat_cfdi_3_3_c_regimenfiscal",
]
RFC_GENERICOS = ("XAXX", "XEXX")
RFC_NOTA = re.compile(r"RFC del sistema anterior: ([A-ZÑ&0-9]+)")


CORRECCIONES_PROVEEDORES = "correcciones_proveedores.csv"


def leer_asociados(directorio):
    """Clientes y proveedores de scv_web (asociados.tsv). Si existe
    <directorio>/correcciones_proveedores.csv (id_asociado, nombre_fiscal,
    rfc, regimen), su RFC y régimen sustituyen a los de scv_web: son los
    proveedores que tenían el RFC o el régimen mal capturado y que el usuario
    corrigió para poder darlos de alta (2026-10-27). Un régimen vacío deja el
    de scv_web."""
    asociados = {}
    for fila in leer_tsv(directorio, "asociados", COLUMNAS_ASOCIADO):
        lista = fila["lista_precio"]
        fila["lista_precio"] = int(lista) if lista and lista.isdigit() else None
        # scv_web los guarda con 4 y 6 decimales; Cliente y Proveedor, con 2.
        fila["descuento"] = decimal(fila["descuento"])
        fila["limite_credito"] = decimal(fila["limite_credito"])
        asociados[int(fila["id"])] = fila

    correcciones = Path(directorio) / CORRECCIONES_PROVEEDORES
    if correcciones.exists():
        with open(correcciones, encoding="utf-8-sig", newline="") as archivo:
            for correccion in csv.DictReader(archivo):
                fila = asociados.get(int(correccion["id_asociado"]))
                if fila is None:
                    continue
                if (correccion.get("rfc") or "").strip():
                    fila["rfc"] = correccion["rfc"].strip()
                if (correccion.get("regimen") or "").strip():
                    fila["sat_cfdi_3_3_c_regimenfiscal"] = correccion["regimen"].strip()
    return asociados


def _rfc_util(rfc):
    return len(rfc) >= 12 and not rfc.startswith(RFC_GENERICOS)


class ClientesLegado:
    """id de asociado de scv_web -> pk de Cliente. Orden: RFC (el del
    cliente o la nota "RFC del sistema anterior" que dejó la importación de
    clientes), nombre único, y si no, se crea con import_legacy_clientes."""

    def __init__(self, asociados, crear):
        from apps.clientes.management.commands.import_legacy_clientes import (
            Command as ImportClientes, LISTA_PRECIO_POR_INDICE,
        )

        self.asociados = asociados
        self.crear = crear
        self._importador = ImportClientes()
        self._listas = {i: ListaPrecio.objects.filter(nombre=n).first() for i, n in LISTA_PRECIO_POR_INDICE.items()}
        self._rfcs_usados = set()
        self._stats = {"sin_rfc": 0, "credito_bandera_gano": 0}
        self.por_rfc, self.por_nombre = {}, {}
        for pk, nombre, nombre_fiscal, rfc, obs in Cliente.objects.order_by("pk").values_list(
            "pk", "nombre", "nombre_fiscal", "rfc", "observaciones"
        ):
            nota = RFC_NOTA.search(obs or "")
            for valor in {normalizar_rfc(rfc), nota.group(1) if nota else ""} - {""}:
                self.por_rfc.setdefault(valor, pk)
            for valor in {normalizar_nombre(nombre), normalizar_nombre(nombre_fiscal)} - {""}:
                self.por_nombre.setdefault(valor, []).append(pk)
        self._cache = {}
        self.resultado = {"rfc": 0, "nombre": 0, "nombre_ambiguo": 0, "creado": 0, "error": 0}
        self.errores = []

    def pk_de(self, id_asociado):
        if id_asociado not in self._cache:
            self._cache[id_asociado] = self._resolver(id_asociado)
        return self._cache[id_asociado]

    def _resolver(self, id_asociado):
        fila = self.asociados.get(id_asociado)
        if fila is None:
            self.resultado["error"] += 1
            self.errores.append(f"asociado {id_asociado}: no viene en asociados.tsv")
            return None
        rfc = normalizar_rfc(fila["rfc"])
        if _rfc_util(rfc) and rfc in self.por_rfc:
            self.resultado["rfc"] += 1
            return self.por_rfc[rfc]
        candidatos = self.por_nombre.get(normalizar_nombre(fila["nombre_fiscal"]), [])
        if candidatos:
            self.resultado["nombre" if len(candidatos) == 1 else "nombre_ambiguo"] += 1
            return candidatos[0]
        self.resultado["creado"] += 1
        if not self.crear:
            return 0  # marcador de "se crearía" en el dry-run
        try:
            cliente = self._importador._crear_cliente(fila, self._listas, self._rfcs_usados, self._stats)
        except Exception as exc:  # noqa: BLE001 - se reporta y la venta se omite
            self.resultado["creado"] -= 1
            self.resultado["error"] += 1
            self.errores.append(f"asociado {id_asociado} {fila['nombre_fiscal']!r}: {exc}")
            return None
        self.por_nombre[normalizar_nombre(cliente.nombre)] = [cliente.pk]
        return cliente.pk


class ProveedoresLegado:
    """id de asociado de scv_web -> pk de Proveedor: por RFC, por nombre, y
    si no, se crea con import_legacy_proveedores (que exige RFC y régimen
    válidos; los que no pasan se reportan y su compra se omite)."""

    def __init__(self, asociados, crear):
        from apps.fiscal.models import RegimenFiscal
        from apps.proveedores.management.commands.import_legacy_proveedores import (
            Command as ImportProveedores,
        )

        self.asociados = asociados
        self.crear = crear
        self._importador = ImportProveedores()
        self._regimenes = {r.clave: r for r in RegimenFiscal.objects.all()}
        self._rfcs = set()
        self._stats = {"ignorados_no_proveedor": 0, "regimen_ajustado_601": 0, "ajustes": []}
        self.por_rfc, self.por_nombre = {}, {}
        for pk, rfc, nombre in Proveedor.objects.order_by("pk").values_list("pk", "rfc", "nombre_fiscal"):
            if rfc:
                self.por_rfc.setdefault(normalizar_rfc(rfc), pk)
            self.por_nombre.setdefault(normalizar_nombre(nombre), pk)
        self._cache = {}
        self.resultado = {"rfc": 0, "nombre": 0, "creado": 0, "error": 0}
        self.errores = []

    def pk_de(self, id_asociado):
        if id_asociado not in self._cache:
            self._cache[id_asociado] = self._resolver(id_asociado)
        return self._cache[id_asociado]

    def _resolver(self, id_asociado):
        fila = self.asociados.get(id_asociado)
        if fila is None:
            self.resultado["error"] += 1
            self.errores.append(f"asociado {id_asociado}: no viene en asociados.tsv")
            return None
        rfc = normalizar_rfc(fila["rfc"])
        if rfc and rfc in self.por_rfc:
            self.resultado["rfc"] += 1
            return self.por_rfc[rfc]
        nombre = normalizar_nombre(fila["nombre_fiscal"])
        if nombre in self.por_nombre:
            self.resultado["nombre"] += 1
            return self.por_nombre[nombre]
        try:
            # El importador original valida RFC y régimen con full_clean() antes
            # de guardar: en el dry-run se corre dentro de un savepoint que se
            # revierte, para saber cuáles sí se podrían crear.
            from django.db import transaction

            with transaction.atomic():
                resultado = self._importador._crear_proveedor(
                    f"asociado {id_asociado}", fila, self._regimenes, self._regimenes.get("601"),
                    self._rfcs, self._stats,
                )
                if resultado != "creado":
                    raise ValueError(f"el asociado es de tipo {fila['tipo']!r}, no PROVEEDOR")
                pk = Proveedor.objects.get(rfc=self._importador_rfc(fila)).pk
                if not self.crear:
                    raise _Revertir()
        except _Revertir:
            self.resultado["creado"] += 1
            return 0
        except Exception as exc:  # noqa: BLE001 - se reporta y la compra se omite
            self.resultado["error"] += 1
            self.errores.append(f"asociado {id_asociado} {fila['nombre_fiscal']!r} rfc={fila['rfc']!r}: {exc}")
            return None
        self.resultado["creado"] += 1
        self.por_nombre[nombre] = pk
        return pk

    @staticmethod
    def _importador_rfc(fila):
        from apps.proveedores.management.commands.import_legacy_proveedores import normalize_rfc

        return normalize_rfc(fila["rfc"])


class VendedoresLegado:
    """id de usuario de scv_web (documento.id_vendedor) -> pk de un User de
    sitordillo, para atribuir las comisiones de las ventas históricas
    (Venta.created_by, ver comisiones.views.reporte_views). Decisión del
    usuario: cada vendedor es un usuario inactivo -sin contraseña ni acceso,
    se activa a mano si llega a operar aquí-, y las personas con dos usuarios
    en scv_web (mismo nombre, p. ej. MARLIT o ANIBAL) se unifican en uno."""

    def __init__(self, directorio, crear):
        from django.contrib.auth import get_user_model

        self.User = get_user_model()
        self.crear = crear
        self.creados = []
        filas = sorted(leer_tsv(directorio, "vendedores", ["id", "login", "nombre"]), key=lambda f: int(f["id"]))
        usados = {u.lower() for u in self.User.objects.values_list("username", flat=True)}
        por_nombre = {
            normalizar_nombre(f"{n} {a}"): pk
            for pk, n, a in self.User.objects.values_list("pk", "first_name", "last_name")
            if normalizar_nombre(f"{n} {a}")
        }
        self._por_id = {}
        for fila in filas:
            nombre = normalizar_nombre(fila["nombre"]) or normalizar_nombre(fila["login"])
            if nombre not in por_nombre:
                por_nombre[nombre] = self._crear(fila, nombre, usados)
            self._por_id[int(fila["id"])] = por_nombre[nombre]

    def _crear(self, fila, nombre, usados):
        base = re.sub(r"[^a-z0-9._-]", "", texto(fila["login"]).lower()) or f"vendedor{fila['id']}"
        username, n = base, 2
        while username in usados:
            username, n = f"{base}{n}", n + 1
        usados.add(username)
        self.creados.append(f"{username} ({nombre})")
        if not self.crear:
            return 0  # marcador de "se crearía" en el dry-run
        usuario = self.User(username=username, first_name=nombre[:150], is_active=False)
        usuario.set_unusable_password()
        usuario.save()
        return usuario.pk

    def pk_de(self, id_vendedor):
        return self._por_id.get(int(id_vendedor or 0))


class _Revertir(Exception):
    pass
