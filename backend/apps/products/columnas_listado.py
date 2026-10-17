"""Columnas y agrupaciones del listado de Productos que cada usuario puede
personalizar, como "Columnas" y "Agrupar por" del sistema anterior
(grid_con_producto): el usuario elige qué columnas ver y en qué orden, y
si los productos se agrupan por uno o varios campos con el conteo de cada
grupo. La elección se guarda por usuario en core.PreferenciaListado y la
respeta también la descarga a Excel (ver export_views.py)."""

from dataclasses import dataclass
from typing import Any, Callable

from django.db.models import Count, DecimalField, F, OuterRef, Subquery

from apps.core.models import PreferenciaListado

from .models import ALMACEN_CEDIS, PRECIO_POSICIONES, Almacen, Producto, ProductoPrecio

VISTA = "products:product-list"

NOMBRES_LISTA = {
    "PUBLICO": "Público",
    "MEDIO MAYOREO": "Medio mayoreo",
    "MAYOREO": "Mayoreo",
    "SUB DISTRIBUIDOR": "Sub distribuidor",
    "PROMOCION": "Promoción",
}


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    # Valor "crudo" del producto (número, fecha o texto); el formato lo pone
    # la plantilla según `formato` y el Excel lo escribe tal cual.
    valor: Callable[[Producto], Any]
    # texto | codigo | nombre | estado | moneda | costo | porcentaje | numero | fecha
    formato: str = "texto"
    relaciones: tuple = ()
    # Como el Costo del sistema anterior: siempre visible, solo se reordena.
    fija: bool = False

    @property
    def numerica(self):
        return self.formato in ("moneda", "costo", "porcentaje", "numero")


def _nombre(relacion, atributo="nombre"):
    def leer(producto):
        objeto = getattr(producto, relacion)
        return getattr(objeto, atributo) if objeto is not None else ""
    return leer


def _filtro_posicion(nombre_lista, nombre_almacen):
    filtro = {"lista_precio__nombre": nombre_lista}
    if nombre_almacen is None:
        filtro["almacen__isnull"] = True
    elif nombre_almacen == ALMACEN_CEDIS:
        filtro["almacen__tipo"] = Almacen.Tipo.CEDIS
    else:
        filtro["almacen__nombre"] = nombre_almacen
    return filtro


def _titulo_posicion(nombre_lista, nombre_almacen):
    titulo = NOMBRES_LISTA.get(nombre_lista, nombre_lista.capitalize())
    if nombre_almacen is None:
        return titulo
    sucursal = nombre_almacen if nombre_almacen == ALMACEN_CEDIS else nombre_almacen.title()
    return f"{titulo} {sucursal}"


def _anotado(campo):
    return lambda producto: getattr(producto, campo, None)


COLUMNAS_BASE = [
    Columna("folio", "Clave", lambda p: p.folio, "codigo"),
    Columna("sku", "Código", lambda p: p.sku, "codigo"),
    Columna("codigo_barras", "Código de barras", lambda p: p.codigo_barras or "", "codigo"),
    Columna("codigo_proveedor", "Código proveedor", lambda p: p.codigo_proveedor, "codigo"),
    Columna("nombre", "Nombre", lambda p: p.nombre, "nombre", ("unidad_medida_auxiliar",)),
    Columna("tipo", "Tipo", lambda p: p.get_tipo_display(), relaciones=("almacen",)),
    Columna("unidad", "Unidad", _nombre("unidad_medida"), relaciones=("unidad_medida",)),
    Columna("contenido", "Contenido", lambda p: p.contenido_display, relaciones=("unidad_medida_auxiliar",)),
    Columna("estado", "Estado", lambda p: "Activo" if p.is_active else "Inactivo", "estado"),
    Columna("costo", "Costo", lambda p: p.precio_costo, "costo", fija=True),
    Columna("precio_venta", "Precio de venta", lambda p: p.precio_venta, "moneda"),
    Columna("iva", "IVA", lambda p: p.tasa_iva if p.tipo_iva == Producto.TipoIVA.GRAVADO else None, "porcentaje"),
    Columna("ieps", "IEPS", lambda p: p.tasa_ieps if p.aplica_ieps else None, "porcentaje"),
    Columna("linea", "Línea", _nombre("linea"), relaciones=("linea",)),
    Columna("marca", "Marca", _nombre("marca"), relaciones=("marca",)),
    Columna("categoria", "Categoría", _nombre("categoria"), relaciones=("categoria",)),
    Columna("subcategoria", "Subcategoría", _nombre("subcategoria"), relaciones=("subcategoria",)),
    Columna("clase", "Clase", _nombre("clase"), relaciones=("clase",)),
    Columna("proveedor", "Proveedor", _nombre("proveedor", "display_name"), relaciones=("proveedor",)),
    Columna("clave_sat", "Clave SAT", _nombre("clave_prod_serv_sat", "clave"), "codigo", ("clave_prod_serv_sat",)),
    Columna("costeo", "Costeo", lambda p: p.get_costeo_display()),
    Columna("stock_minimo", "Stock mínimo", lambda p: p.stock_minimo, "numero"),
    Columna("stock_maximo", "Stock máximo", lambda p: p.stock_maximo, "numero"),
    Columna("peso", "Peso (kg)", lambda p: p.peso, "numero"),
    Columna("dias_reserva", "Días de reserva", lambda p: p.dias_reserva, "numero"),
    Columna("modificacion", "Modificación", lambda p: p.updated_at, "fecha"),
]

# Precio y % de utilidad de cada lista, en el mismo orden canónico de la
# lista de precios (Precio 1..N / Utilidad 1..N del sistema anterior).
COLUMNAS_PRECIO = [
    Columna(f"precio_{posicion}", _titulo_posicion(lista, almacen), _anotado(f"col_precio_{posicion}"), "moneda")
    for posicion, lista, almacen in PRECIO_POSICIONES
]
COLUMNAS_UTILIDAD = [
    Columna(
        f"utilidad_{posicion}", f"Utilidad {_titulo_posicion(lista, almacen)}",
        _anotado(f"col_utilidad_{posicion}"), "porcentaje",
    )
    for posicion, lista, almacen in PRECIO_POSICIONES
]

COLUMNAS = {columna.clave: columna for columna in COLUMNAS_BASE + COLUMNAS_PRECIO + COLUMNAS_UTILIDAD}

COLUMNAS_DEFAULT = [
    "sku", "nombre", "tipo", "unidad", "estado", "costo",
    "precio_1", "precio_2", "precio_3", "precio_4", "precio_5",
]


@dataclass(frozen=True)
class Agrupacion:
    clave: str
    titulo: str
    lookup: str
    sin_valor: str = ""

    def etiqueta(self, valor):
        if self.clave == "tipo":
            return Producto.TipoProducto(valor).label if valor in Producto.TipoProducto.values else valor
        if self.clave == "estado":
            return "Activos" if valor else "Inactivos"
        return valor if valor not in (None, "") else self.sin_valor


AGRUPACIONES = {
    agrupacion.clave: agrupacion
    for agrupacion in [
        Agrupacion("linea", "Línea", "linea__nombre", "Sin línea"),
        Agrupacion("marca", "Marca", "marca__nombre", "Sin marca"),
        Agrupacion("categoria", "Categoría", "categoria__nombre", "Sin categoría"),
        Agrupacion("clase", "Clase", "clase__nombre", "Sin clase"),
        Agrupacion("unidad", "Unidad de medida", "unidad_medida__nombre", "Sin unidad"),
        Agrupacion("tipo", "Tipo", "tipo"),
        Agrupacion("estado", "Estado", "is_active"),
    ]
}
# "Estático" del sistema anterior: un solo campo de esta lista. "Dinámico":
# uno o varios niveles de AGRUPACIONES, en el orden que se elija.
AGRUPACIONES_ESTATICAS = ["linea", "marca", "categoria", "clase", "unidad"]


def limpiar_columnas(claves):
    """Solo claves del catálogo, sin repetir y con las fijas siempre
    presentes (si faltan, en su lugar de la vista por defecto)."""
    columnas = list(dict.fromkeys(clave for clave in claves if clave in COLUMNAS))
    if not columnas:
        return list(COLUMNAS_DEFAULT)
    for clave, columna in COLUMNAS.items():
        if columna.fija and clave not in columnas:
            posicion = COLUMNAS_DEFAULT.index(clave) if clave in COLUMNAS_DEFAULT else len(columnas)
            columnas.insert(min(posicion, len(columnas)), clave)
    return columnas


def limpiar_agrupar(claves):
    return list(dict.fromkeys(clave for clave in claves if clave in AGRUPACIONES))


def preferencia_de(usuario):
    """(claves de columnas, claves de agrupación) que eligió el usuario, o
    las de por defecto."""
    preferencia = PreferenciaListado.objects.filter(usuario=usuario, vista=VISTA).first()
    if preferencia is None:
        return list(COLUMNAS_DEFAULT), []
    return limpiar_columnas(preferencia.columnas), limpiar_agrupar(preferencia.agrupar)


def guardar_preferencia(usuario, *, columnas=None, agrupar=None):
    preferencia, _ = PreferenciaListado.objects.get_or_create(
        usuario=usuario, vista=VISTA, defaults={"columnas": list(COLUMNAS_DEFAULT)},
    )
    if columnas is not None:
        preferencia.columnas = limpiar_columnas(columnas)
    if agrupar is not None:
        preferencia.agrupar = limpiar_agrupar(agrupar)
    preferencia.save()
    return preferencia


def preparar_queryset(queryset, claves_columnas, claves_agrupar):
    """Agrega al queryset (ya filtrado) solo lo que piden las columnas
    elegidas -las relaciones y un subquery por cada precio/utilidad- y lo
    ordena por los campos de agrupación y luego por nombre."""
    relaciones = {relacion for clave in claves_columnas for relacion in COLUMNAS[clave].relaciones}
    if relaciones:
        queryset = queryset.select_related(*sorted(relaciones))

    anotaciones = {}
    for posicion, lista, almacen in PRECIO_POSICIONES:
        for prefijo, campo in (("precio", "precio_con_impuesto"), ("utilidad", "utilidad_pct")):
            if f"{prefijo}_{posicion}" not in claves_columnas:
                continue
            anotaciones[f"col_{prefijo}_{posicion}"] = Subquery(
                ProductoPrecio.objects.filter(producto_id=OuterRef("pk"), **_filtro_posicion(lista, almacen))
                .values(campo)[:1],
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
    if anotaciones:
        queryset = queryset.annotate(**anotaciones)

    if claves_agrupar:
        queryset = queryset.annotate(**{
            f"grupo_{clave}": F(AGRUPACIONES[clave].lookup) for clave in claves_agrupar
        })
        orden = [F(f"grupo_{clave}").asc(nulls_last=True) for clave in claves_agrupar]
        queryset = queryset.order_by(*orden, "nombre", "pk")
    return queryset


def conteos_por_grupo(queryset, claves_agrupar):
    """{(valor nivel 1, ..., valor nivel N): productos} para cada nivel, sobre
    TODO el resultado filtrado -no solo la página- para que el encabezado de
    cada grupo diga cuántos productos tiene en total."""
    conteos = {}
    lookups = [AGRUPACIONES[clave].lookup for clave in claves_agrupar]
    for nivel in range(1, len(lookups) + 1):
        campos = lookups[:nivel]
        for fila in queryset.order_by().values(*campos).annotate(n=Count("pk")):
            conteos[tuple(fila[campo] for campo in campos)] = fila["n"]
    return conteos


def filas_agrupadas(productos, claves_agrupar, conteos):
    """Intercala, entre los productos (ya ordenados por los campos de
    agrupación), un encabezado cada vez que cambia el valor de un nivel.
    Cada fila lleva `grupos`: los ids de los encabezados que la contienen,
    para poder colapsar un grupo completo (listado-personalizable.js)."""
    filas = []
    anterior = None
    abiertos = []
    siguiente_id = 0
    for producto in productos:
        llave = tuple(getattr(producto, f"grupo_{clave}") for clave in claves_agrupar)
        cambia_desde = 0
        if anterior is not None:
            while cambia_desde < len(llave) and llave[cambia_desde] == anterior[cambia_desde]:
                cambia_desde += 1
        abiertos = abiertos[:cambia_desde]
        for nivel in range(cambia_desde, len(llave)):
            siguiente_id += 1
            grupo_id = f"g{siguiente_id}"
            agrupacion = AGRUPACIONES[claves_agrupar[nivel]]
            filas.append({
                "es_grupo": True,
                "id": grupo_id,
                "nivel": nivel,
                "grupos": " ".join(abiertos),
                "titulo": agrupacion.titulo,
                "valor": agrupacion.etiqueta(llave[nivel]),
                "conteo": conteos.get(llave[:nivel + 1], 0),
            })
            abiertos.append(grupo_id)
        filas.append({"es_grupo": False, "producto": producto, "grupos": " ".join(abiertos)})
        anterior = llave
    return filas
