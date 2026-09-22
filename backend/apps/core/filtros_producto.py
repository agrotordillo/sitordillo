"""Filtros por línea, marca, clase, categoría, subcategoría y sucursal,
compartidos por todos los listados que pivotan sobre Producto (Productos,
Lotes, Existencias, y los que se vayan sumando después). Antes cada
pantalla reimplementaba a mano la misma lectura de GET y el mismo
catálogo de opciones; esto centraliza esa lógica en un solo lugar para
que agregar o corregir un filtro no signifique tocar N vistas.

Se ofrecen dos formas de usarlo:
- Las funciones sueltas (`leer_filtros_producto`, `aplicar_filtros_producto`,
  `aplicar_filtro_almacen`, `contexto_filtros_producto`), para vistas con
  un get_queryset() ya complejo (agregaciones, function-based views, etc.)
  donde conviene llamar cada paso a mano.
- `FiltrosProductoMixin`, para un ListView estándar: agrega los filtros
  automáticamente a get_queryset()/get_context_data() vía la cadena de
  super(), sin que la vista tenga que llamar nada explícitamente (aunque
  también puede llamarlas a mano si su get_queryset() no pasa por
  super().get_queryset(), ver ExistenciaListView)."""

from apps.core.scoping import almacenes_visibles
from apps.products.models import Almacen, Categoria, Clase, Linea, Marca, Subcategoria

# Nombres de parámetro GET, consistentes en todas las pantallas: cambiar
# uno aquí basta para que todos los listados que usan el helper lo reflejen.
CAMPOS_FILTRO_PRODUCTO = ("marca", "linea", "categoria", "subcategoria", "clase")


def leer_filtros_producto(request, *, incluir_almacen=False):
    """Lee del GET los ids seleccionados para cada filtro, ya "strip()eados".
    Devuelve un dict {"marca": "3", "linea": "", ...}."""
    filtros = {campo: request.GET.get(campo, "").strip() for campo in CAMPOS_FILTRO_PRODUCTO}
    if incluir_almacen:
        filtros["almacen"] = request.GET.get("almacen", "").strip()
    return filtros


def aplicar_filtros_producto(queryset, filtros, *, prefix=""):
    """Aplica al queryset los filtros de marca/línea/categoría/subcategoría/
    clase que vengan con valor. `prefix` es el lookup hasta Producto: ""
    si el queryset ya es de Producto, o algo como "producto__" /
    "lote__producto__" si hay que atravesar una FK primero."""
    for campo in CAMPOS_FILTRO_PRODUCTO:
        valor = filtros.get(campo)
        if valor:
            queryset = queryset.filter(**{f"{prefix}{campo}_id": valor})
    return queryset


def aplicar_filtro_almacen(queryset, filtros, *, campo="almacen"):
    """Aplica el filtro de sucursal si viene seleccionado. `campo` es el
    lookup hasta Almacen (p.ej. "almacen", "lote__almacen",
    "orden_compra__almacen_destino")."""
    valor = filtros.get("almacen")
    if valor:
        queryset = queryset.filter(**{f"{campo}_id": valor})
    return queryset


def contexto_filtros_producto(request, user=None, *, incluir_almacen=False, solo_sucursales=False):
    """Arma, en un solo dict, tanto los ids seleccionados (marca_id,
    linea_id, ...) como los catálogos para poblar los <select> del
    template compartido `core/includes/_filtros_producto.html`. Si se
    pasa `user`, el catálogo de sucursales respeta almacenes_visibles(user),
    igual que ya hacía cada pantalla por su cuenta."""
    filtros = leer_filtros_producto(request, incluir_almacen=incluir_almacen)
    contexto = {f"{campo}_id": valor for campo, valor in filtros.items()}

    contexto["marcas"] = Marca.objects.filter(is_active=True).order_by("nombre")
    contexto["lineas"] = Linea.objects.filter(is_active=True).order_by("nombre")
    contexto["categorias"] = Categoria.objects.filter(is_active=True).order_by("nombre")
    contexto["clases"] = Clase.objects.filter(is_active=True).order_by("nombre")

    categoria_id = filtros.get("categoria")
    contexto["subcategorias"] = (
        Subcategoria.objects.filter(categoria_id=categoria_id, is_active=True).order_by("nombre")
        if categoria_id
        else Subcategoria.objects.none()
    )

    if incluir_almacen:
        almacenes = Almacen.objects.filter(is_active=True)
        if solo_sucursales:
            almacenes = almacenes.filter(tipo=Almacen.Tipo.SUCURSAL)
        visibles = almacenes_visibles(user) if user is not None else None
        if visibles is not None:
            almacenes = almacenes.filter(pk__in=visibles.values_list("pk", flat=True))
        contexto["almacenes"] = almacenes.order_by("nombre")

    contexto["mostrar_filtro_almacen"] = incluir_almacen
    contexto["hay_filtros_producto"] = any(filtros.values())
    return contexto


class FiltrosProductoMixin:
    """Mixin para ListView. Configúralo con estos atributos de clase:

    - filtro_producto_prefix: lookup hasta Producto ("" si el queryset ya
      es de Producto, "producto__" si hay que atravesar una FK).
    - filtro_incluir_almacen: si además se agrega el filtro de sucursal.
    - filtro_almacen_campo: lookup hasta Almacen (por defecto "almacen").
    - filtro_almacen_solo_sucursales: limita el <select> de sucursal a
      tipo "sucursal" (excluye CEDIS), igual que ya hacían algunos reportes.

    Si la vista define su propio get_queryset()/get_context_data() y
    llama a super(), los filtros se aplican solos gracias al orden del
    MRO -no hace falta llamar nada a mano-, siempre que este mixin se
    liste ANTES que ListView en las bases de la clase. Si el
    get_queryset() de la vista no pasa por super().get_queryset() (por
    ejemplo porque arma el queryset base a mano), usa
    self.aplicar_filtros_producto(queryset) explícitamente."""

    filtro_producto_prefix = ""
    filtro_incluir_almacen = False
    filtro_almacen_campo = "almacen"
    filtro_almacen_solo_sucursales = False

    def get_filtros_producto(self):
        if not hasattr(self, "_filtros_producto_cache"):
            self._filtros_producto_cache = leer_filtros_producto(
                self.request, incluir_almacen=self.filtro_incluir_almacen
            )
        return self._filtros_producto_cache

    def aplicar_filtros_producto(self, queryset):
        filtros = self.get_filtros_producto()
        queryset = aplicar_filtros_producto(queryset, filtros, prefix=self.filtro_producto_prefix)
        if self.filtro_incluir_almacen:
            queryset = aplicar_filtro_almacen(queryset, filtros, campo=self.filtro_almacen_campo)
        return queryset

    def get_contexto_filtros_producto(self):
        return contexto_filtros_producto(
            self.request,
            self.request.user,
            incluir_almacen=self.filtro_incluir_almacen,
            solo_sucursales=self.filtro_almacen_solo_sucursales,
        )

    def get_queryset(self):
        return self.aplicar_filtros_producto(super().get_queryset())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_contexto_filtros_producto())
        return context
