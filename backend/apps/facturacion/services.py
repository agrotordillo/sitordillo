from apps.fiscal.models import ClaveProdServSAT, ClaveUnidadSAT

from .facturama_client import FacturamaClient


def buscar_claves_prod_serv(keyword):
    """Busca en el catálogo de Facturama (autoridad: SAT) y devuelve los
    resultados crudos, sin guardarlos todavía."""
    client = FacturamaClient()
    return client.buscar_productos_servicios(keyword)


def buscar_claves_unidad(keyword):
    client = FacturamaClient()
    return client.buscar_unidades(keyword)


def guardar_clave_prod_serv(clave, descripcion):
    obj, _ = ClaveProdServSAT.objects.update_or_create(
        clave=clave,
        defaults={"descripcion": descripcion},
    )
    return obj


def guardar_clave_unidad(clave, nombre, simbolo=""):
    obj, _ = ClaveUnidadSAT.objects.update_or_create(
        clave=clave,
        defaults={"nombre": nombre, "simbolo": simbolo},
    )
    return obj
