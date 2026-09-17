from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import ListaPrecio, ProductoPrecio, Turno


def resolver_precio_producto(producto, lista_precio, almacen=None):
    """Precio de venta vigente de `producto` en `lista_precio`: prioriza el
    precio específico de `almacen` (ProductoPrecio.almacen) sobre el
    general de esa misma lista, ya que un precio por sucursal es más
    específico y debe ganar. Devuelve None si no hay ningún ProductoPrecio
    configurado para esa lista -el llamador decide el respaldo, por
    ejemplo Producto.precio_venta-."""
    precios = ProductoPrecio.objects.filter(producto=producto, lista_precio=lista_precio)
    precio = None
    if almacen is not None:
        precio = precios.filter(almacen=almacen).first()
    if precio is None:
        precio = precios.filter(almacen__isnull=True).first()
    return precio.precio_con_impuesto if precio else None


def resolver_lista_precio_cliente(cliente):
    """Lista de precios que debe aplicarse a un cliente: la suya propia si
    tiene una asignada (su "precio preferencial", ver Cliente.lista_precio),
    o si no "PUBLICO" -el mostrador/caja nunca la elige a mano, ver
    ventas.views.venta_views.VentaCreateView-."""
    if cliente is not None and cliente.lista_precio_id:
        return cliente.lista_precio
    return ListaPrecio.objects.filter(nombre="PUBLICO").first()


def fijar_precios_autorizados(formset, cliente, almacen, valor_estrategia_fifo):
    """Recalcula precio_unitario/lista_precio/descuento/estrategia_salida de
    cada línea de un formset de detalle -de Venta o de Cotización, ambos
    con esos 4 campos- usando la lista de precios del cliente y el precio
    vigente en la sucursal indicada, IGNORANDO lo que haya llegado
    capturado: ni el cajero en una venta ni mostrador en una cotización
    deciden el precio, se resuelve siempre aquí. Se llama sobre un formset
    ya validado (formset.is_valid()), antes de guardarlo.
    `valor_estrategia_fifo` es el valor de FIFO del Estrategia.TextChoices
    del modelo que corresponda (VentaDetalle.Estrategia.FIFO o
    CotizacionDetalle.Estrategia.FIFO): ninguno de los dos flujos permite
    FEFO, siempre es FIFO. Devuelve la lista de precios resuelta, por si
    el llamador la necesita para algo más."""
    lista_precio = resolver_lista_precio_cliente(cliente)
    for f in formset:
        cd = f.cleaned_data
        if not cd or cd.get("DELETE") or not cd.get("producto"):
            continue
        producto = cd["producto"]
        precio = resolver_precio_producto(producto, lista_precio, almacen=almacen) if lista_precio else None
        f.instance.precio_unitario = precio if precio is not None else producto.precio_venta
        f.instance.lista_precio = lista_precio
        f.instance.estrategia_salida = valor_estrategia_fifo
        f.instance.descuento = Decimal("0.00")
    return lista_precio


def abrir_turno(punto_venta, usuario, observaciones=""):
    """Abre un nuevo turno para esa caja (punto de venta de tipo Cobro).
    La restricción de "un solo turno abierto por punto de venta" vive en
    la base de datos (UniqueConstraint condicionado), así que aquí solo se
    traduce el IntegrityError de esa restricción a un mensaje claro -es la
    fuente de verdad ante dos aperturas simultáneas, no una revisión previa
    en Python que dejaría una ventana de carrera-. El try/except queda
    FUERA de cualquier transaction.atomic(): capturarlo dentro dejaría la
    conexión en estado de rollback pendiente para lo que siga en esa misma
    transacción."""
    turno = Turno(punto_venta=punto_venta, usuario=usuario, observaciones=observaciones)
    turno.full_clean()
    try:
        turno.save()
    except IntegrityError:
        raise ValidationError("Este punto de venta ya tiene un turno abierto.")
    return turno
