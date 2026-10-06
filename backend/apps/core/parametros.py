"""Lectura segura de parámetros que llegan en la URL (GET) o en un JSON.

Un id, número o fecha mal formado no debe tumbar la pantalla con un error
500 (B28 en docs/AUDITORIA.md): `?almacen=abc` hacía que Postgres rechazara
la consulta, `?fecha_desde=2026-02-30` hacía que parse_date lanzara
ValueError, y un id gigantesco desbordaba la columna. Todas las vistas leen
sus filtros con estas funciones en vez de pasarlos crudos al ORM.

Criterio común: un parámetro vacío es "sin filtro"; uno inválido en un
filtro por id no muestra nada (filtrar_por_id) -igual que un id que no
existe-, y una fecha inválida se ignora, igual que una mal escrita."""

from django.utils import timezone
from django.utils.dateparse import parse_date

# Las llaves primarias son BigAutoField.
ID_MAXIMO = 2**63 - 1


def entero(valor, *, minimo=None, maximo=None):
    """`valor` como int si es un entero sin signo (solo dígitos ASCII)
    dentro de [minimo, maximo]; si no, None."""
    texto = str(valor).strip() if valor is not None else ""
    if not texto or not texto.isascii() or not texto.isdigit():
        return None
    numero = int(texto)
    if (minimo is not None and numero < minimo) or (maximo is not None and numero > maximo):
        return None
    return numero


def id_valido(valor):
    """`valor` como id de registro (int positivo que cabe en la columna) o None."""
    return entero(valor, minimo=1, maximo=ID_MAXIMO)


def ids_validos(valores):
    """Los ids válidos de una lista (o de un texto separado por comas), sin
    repetir y en el orden en que llegaron. Lo que no es un id se descarta;
    lo que no es una lista ni un texto, da []."""
    if isinstance(valores, str):
        valores = valores.split(",")
    if not isinstance(valores, (list, tuple)):
        return []
    return list(dict.fromkeys(i for i in map(id_valido, valores) if i is not None))


def fecha(valor):
    """`valor` como date (formato AAAA-MM-DD) o None si viene vacío, mal
    escrito o no existe (30 de febrero)."""
    try:
        return parse_date(str(valor or "").strip())
    except ValueError:
        return None


def fecha_filtro(request, param="fecha"):
    """La fecha a mostrar en una lista "de hoy por default" (ventas,
    cotizaciones, pedidos): la de `param` en GET si viene y es válida
    (ver fecha()), si no timezone.localdate() -nunca None, para que la
    lista siempre tenga algo que filtrar sin que el usuario tenga que
    elegir una fecha la primera vez que entra-."""
    return fecha(request.GET.get(param)) or timezone.localdate()


def url_con_fecha(request, fecha_valor, *, param="fecha"):
    """La URL actual (mismo path y demás filtros en la querystring, p. ej.
    "estatus") pero con `param` puesto en `fecha_valor` -para los enlaces
    de "día anterior/siguiente/hoy" de una lista filtrada por fecha, sin
    tirar otros filtros ya aplicados-."""
    query = request.GET.copy()
    query[param] = fecha_valor.isoformat()
    return f"{request.path}?{query.urlencode()}"


def filtrar_por_id(queryset, lookup, valor):
    """Aplica `lookup=valor` si `valor` trae algo: vacío no filtra, un id
    válido filtra, y uno inválido deja el queryset vacío."""
    texto = str(valor or "").strip()
    if not texto:
        return queryset
    pk = id_valido(texto)
    return queryset.filter(**{lookup: pk}) if pk is not None else queryset.none()
