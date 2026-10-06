# La búsqueda en el catálogo SAT de Facturama es de solo lectura y se deja
# abierta a cualquier usuario autenticado. Agregar una clave al catálogo
# local sí escribe -y su descripción se muestra después en el formulario de
# producto-, así que exige poder crear o editar productos (B07 en
# docs/AUDITORIA.md).
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from apps.facturacion.facturama_client import FacturamaError
from apps.facturacion.services import (
    buscar_claves_prod_serv,
    buscar_claves_unidad,
    guardar_clave_prod_serv,
    guardar_clave_unidad,
)
from apps.products.permisos import puede_editar_productos


def _agregar_al_catalogo(request, q, guardar):
    if not puede_editar_productos(request.user):
        raise PermissionDenied
    clave = request.POST.get("clave", "").strip()
    etiqueta = request.POST.get("etiqueta", "").strip()
    if clave and etiqueta:
        guardar(clave, etiqueta)
        messages.success(request, f"Clave {clave} agregada al catálogo local.")
    return redirect(f"{request.path}?{urlencode({'q': q})}")


def buscar_clave_prod_serv_view(request):
    q = request.GET.get("q", "").strip()

    if request.method == "POST":
        return _agregar_al_catalogo(request, q, guardar_clave_prod_serv)

    resultados = []
    if q:
        try:
            crudos = buscar_claves_prod_serv(q)
            resultados = [{"clave": r["Value"], "etiqueta": r["Name"]} for r in crudos]
        except FacturamaError as e:
            messages.error(request, f"No se pudo consultar el catálogo de Facturama: {e}")

    return render(
        request,
        "facturacion/buscar_catalogo_sat.html",
        {
            "titulo": "Buscar clave de producto o servicio SAT",
            "q": q,
            "resultados": resultados,
            "puede_agregar": puede_editar_productos(request.user),
            "active_module": "products",
        },
    )


def buscar_clave_unidad_view(request):
    q = request.GET.get("q", "").strip()

    if request.method == "POST":
        return _agregar_al_catalogo(request, q, guardar_clave_unidad)

    resultados = []
    if q:
        try:
            crudos = buscar_claves_unidad(q)
            resultados = [{"clave": r["Value"], "etiqueta": r["Name"]} for r in crudos]
        except FacturamaError as e:
            messages.error(request, f"No se pudo consultar el catálogo de Facturama: {e}")

    return render(
        request,
        "facturacion/buscar_catalogo_sat.html",
        {
            "titulo": "Buscar clave de unidad SAT",
            "q": q,
            "resultados": resultados,
            "puede_agregar": puede_editar_productos(request.user),
            "active_module": "products",
        },
    )
