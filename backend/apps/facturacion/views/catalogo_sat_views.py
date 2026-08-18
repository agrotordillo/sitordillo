from django.contrib import messages
from django.shortcuts import redirect, render

from apps.facturacion.facturama_client import FacturamaError
from apps.facturacion.services import (
    buscar_claves_prod_serv,
    buscar_claves_unidad,
    guardar_clave_prod_serv,
    guardar_clave_unidad,
)


def buscar_clave_prod_serv_view(request):
    q = request.GET.get("q", "").strip()

    if request.method == "POST":
        clave = request.POST.get("clave")
        etiqueta = request.POST.get("etiqueta")
        if clave and etiqueta:
            guardar_clave_prod_serv(clave, etiqueta)
            messages.success(request, f"Clave {clave} agregada al catálogo local.")
        return redirect(f"{request.path}?q={q}")

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
            "active_module": "products",
        },
    )


def buscar_clave_unidad_view(request):
    q = request.GET.get("q", "").strip()

    if request.method == "POST":
        clave = request.POST.get("clave")
        etiqueta = request.POST.get("etiqueta")
        if clave and etiqueta:
            guardar_clave_unidad(clave, etiqueta)
            messages.success(request, f"Clave {clave} agregada al catálogo local.")
        return redirect(f"{request.path}?q={q}")

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
            "active_module": "products",
        },
    )
