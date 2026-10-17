"""Búsqueda de productos por nombre y SKU (código), la misma en todos los
buscadores de producto de los formularios (producto-search.js ->
api:producto-buscar) y en el "Buscar" de los listados que pivotan sobre
Producto.

- Cada palabra se busca por separado: "sulfa 100" encuentra "3 SULFA
  INYECTABLE 100ML" (antes se buscaba el texto completo junto y no
  aparecía).
- Un texto corto (1-2 caracteres) solo encuentra el SKU o código de barras
  exacto: hay SKUs de una o dos letras ("E", "CM", "03") que antes no se
  podían buscar, y por nombre dos letras traen media base."""

from django.db.models import Case, IntegerField, Q, Value, When

MIN_CARACTERES_NOMBRE = 3


def q_busqueda_producto(texto, prefijo=""):
    """Q para filtrar por `texto`. `prefijo` es el lookup hasta Producto
    ("" si el queryset ya es de Producto, "producto__" si se atraviesa una
    FK). Con texto vacío regresa un Q() que no filtra nada."""
    texto = (texto or "").strip()
    if not texto:
        return Q()

    exacto = Q(**{f"{prefijo}sku__iexact": texto}) | Q(**{f"{prefijo}codigo_barras__iexact": texto})
    if len(texto) < MIN_CARACTERES_NOMBRE:
        return exacto

    por_palabras = Q()
    for palabra in texto.split():
        por_palabras &= (
            Q(**{f"{prefijo}nombre__icontains": palabra})
            | Q(**{f"{prefijo}sku__icontains": palabra})
            | Q(**{f"{prefijo}folio__icontains": palabra})
            | Q(**{f"{prefijo}codigo_barras__icontains": palabra})
        )
    return exacto | por_palabras


def buscar_productos(queryset, texto, prefijo=""):
    return queryset.filter(q_busqueda_producto(texto, prefijo))


def ordenar_por_coincidencia(queryset, texto):
    """Primero el SKU/código exacto, luego los SKU que empiezan con el
    texto, luego los nombres que empiezan con él y al final el resto; cada
    bloque por nombre."""
    texto = (texto or "").strip()
    relevancia = Case(
        When(Q(sku__iexact=texto) | Q(codigo_barras__iexact=texto), then=Value(0)),
        When(sku__istartswith=texto, then=Value(1)),
        When(nombre__istartswith=texto, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )
    return queryset.annotate(relevancia=relevancia).order_by("relevancia", "nombre")
