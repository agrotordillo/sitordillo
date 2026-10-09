"""Recordar los últimos filtros de cada pantalla de listado.

Decisión del usuario: los filtros de un listado se conservan siempre al
volver a esa pantalla -desde el menú, al regresar de un registro o en
otra visita dentro de la misma sesión-, no solo al paginar o al guardar y
cancelar una edición. Se guardan en la sesión (por usuario y por pantalla)
y "Limpiar filtros" los borra.

Cómo funciona (FiltrosRecordadosMiddleware), solo para GET a las vistas
de VISTAS_CON_FILTROS:
- Con filtros en la URL: se guardan (sin "page" ni valores vacíos) y la
  vista responde normal.
- Sin nada en la URL y con filtros guardados: redirige a la misma pantalla
  con esos filtros, y la pantalla muestra el aviso "Mostrando tus últimos
  filtros · Limpiar filtros" (core/includes/_filtros_recordados.html).
- Con ?limpiar_filtros=1: borra los guardados y redirige a la pantalla sin
  filtros. Todos los botones de "Limpiar" de los listados apuntan ahí: un
  enlace a la URL sola volvería a aplicar lo guardado.
"""
from django.shortcuts import redirect

# Nombres de URL de las pantallas de listado/reporte con filtros por GET.
VISTAS_CON_FILTROS = frozenset({
    "products:product-list",
    "proveedores:supplier-list",
    "clientes:cliente-list",
    "compras:orden-list",
    "compras:analisis-producto",
    "compras:analisis-anual",
    "inventario:lote-list",
    "inventario:existencia-list",
    "inventario:surtimiento-list",
    "inventario:kardex-producto",
    "inventario:existencia-sin-movimiento",
    "inventario:movimiento-costo-list",
    "inventario:costeo-producto-list",
    "inventario:movimiento-almacen-list",
    "cotizaciones:cotizacion-list",
    "pedidos:pedido-list",
    "ventas:venta-list",
    "cobros:cuenta-list",
    "comisiones:reporte",
    "comisiones_ruta:reporte",
    "pagos:cuenta-list",
    "pagos:recibo-list",
    "gastos:reporte",
})

PARAMETRO_LIMPIAR = "limpiar_filtros"
# Parámetros que no son filtros: la página se recalcula al volver.
_NO_SON_FILTROS = {"page", PARAMETRO_LIMPIAR}
# Listas que sin fecha en la URL muestran el día de hoy (ver
# apps.core.filtros_fecha): recordar la fecha haría que al día siguiente
# abrieran en el día anterior. Se recuerdan sus demás filtros, no el día.
_NO_RECORDAR_POR_VISTA = {
    "ventas:venta-list": {"fecha"},
    "cotizaciones:cotizacion-list": {"fecha"},
    "pedidos:pedido-list": {"fecha"},
}
_CLAVE_SESION = "filtros_recordados"
_CLAVE_RESTAURADOS = "filtros_recordados_aviso"


def _filtros_de(querydict, nombre_vista):
    excluidos = _NO_SON_FILTROS | _NO_RECORDAR_POR_VISTA.get(nombre_vista, set())
    filtros = querydict.copy()
    for clave in list(filtros.keys()):
        if clave in excluidos:
            del filtros[clave]
        else:
            valores = [v for v in filtros.getlist(clave) if v.strip()]
            if valores:
                filtros.setlist(clave, valores)
            else:
                del filtros[clave]
    return filtros


class FiltrosRecordadosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if (
            request.method != "GET"
            or match is None
            or match.view_name not in VISTAS_CON_FILTROS
            or not getattr(request, "user", None)
            or not request.user.is_authenticated
        ):
            return None

        guardados = request.session.get(_CLAVE_SESION, {})
        nombre = match.view_name

        if PARAMETRO_LIMPIAR in request.GET:
            if guardados.pop(nombre, None) is not None:
                request.session[_CLAVE_SESION] = guardados
            return redirect(request.path)

        if request.GET:
            filtros = _filtros_de(request.GET, nombre)
            if filtros:
                guardados[nombre] = filtros.urlencode()
                request.session[_CLAVE_SESION] = guardados
            elif (
                set(request.GET.keys()) - _NO_SON_FILTROS - _NO_RECORDAR_POR_VISTA.get(nombre, set())
                and guardados.pop(nombre, None) is not None
            ):
                # Se enviaron los filtros vacíos a propósito (formulario
                # limpiado a mano): equivale a limpiar.
                request.session[_CLAVE_SESION] = guardados
            # Aviso solo en la respuesta que vino de restaurar los filtros.
            request.filtros_restaurados = request.session.pop(_CLAVE_RESTAURADOS, None) == nombre
            return None

        if nombre in guardados:
            request.session[_CLAVE_RESTAURADOS] = nombre
            return redirect(f"{request.path}?{guardados[nombre]}")
        return None
