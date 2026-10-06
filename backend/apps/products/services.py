from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import ListaPrecio, ProductoPrecio, PuntoVenta, Turno


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


LISTA_PROMOCION = "PROMOCION"


def resolver_precio_linea(producto, lista_cliente, almacen):
    """(precio_unitario, lista_precio) con que se cobra `producto`: el de
    la lista del cliente en `almacen` (ver resolver_precio_producto) o, si
    esa lista no tiene uno configurado, Producto.precio_venta.

    Un paquete (combo) es una promoción: se cobra SIEMPRE con la lista
    PROMOCION, sin importar la del cliente (B25 en docs/AUDITORIA.md,
    decisión del usuario). Si el paquete todavía no tiene precio en esa
    lista, se resuelve como cualquier producto. Devuelve también la lista
    que de verdad se usó, porque se registra en la línea (la comisión por
    colaborador depende de ella)."""
    if producto.es_paquete:
        promocion = ListaPrecio.objects.filter(nombre=LISTA_PROMOCION).first()
        if promocion is not None:
            precio = resolver_precio_producto(producto, promocion, almacen=almacen)
            if precio is not None:
                return precio, promocion
    precio = resolver_precio_producto(producto, lista_cliente, almacen=almacen) if lista_cliente else None
    return (precio if precio is not None else producto.precio_venta), lista_cliente


def resolver_precio_autorizado(producto, lista_precio, almacen):
    """Solo el precio de resolver_precio_linea."""
    return resolver_precio_linea(producto, lista_precio, almacen)[0]


def fijar_precios_autorizados(formset, cliente, almacen, valor_estrategia_fifo):
    """Recalcula precio_unitario/lista_precio/descuento/estrategia_salida de
    cada línea de un formset de detalle -de Venta, Cotización o Pedido,
    todos con esos 4 campos- usando la lista de precios del cliente y el precio
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
        f.instance.precio_unitario, f.instance.lista_precio = resolver_precio_linea(
            cd["producto"], lista_precio, almacen
        )
        f.instance.estrategia_salida = valor_estrategia_fifo
        f.instance.descuento = Decimal("0.00")
    return lista_precio


def tipos_punto_venta_de(usuario):
    """En qué tipo de punto de venta puede abrir (y cerrar) turno este
    usuario, según los permisos de su rol -asignado en la administración
    de usuarios-: en una caja (Cobro) si puede registrar ventas, y en un
    mostrador (Pedido) si puede levantar cotizaciones o pedidos. Quien
    tiene ambos roles (sucursal chica) puede abrir cualquiera de los dos."""
    tipos = []
    if usuario.has_perm("ventas.add_venta"):
        tipos.append(PuntoVenta.Tipo.COBRO)
    if usuario.has_perm("cotizaciones.add_cotizacion") or usuario.has_perm("pedidos.add_pedido"):
        tipos.append(PuntoVenta.Tipo.PEDIDO)
    return tipos


def turno_abierto_de(usuario, solo_cobro=False):
    """El turno propio y abierto de `usuario`, sin partir de una sucursal
    ya elegida -al revés de como funcionaba antes (ver
    ventas.services.obtener_turno_abierto/validar_turno_abierto, que
    reciben el almacén ya elegido por el cajero): ahora la sucursal de
    una venta o cotización se determina A PARTIR de este turno, así que
    ni venta ni cotización ofrecen un selector de sucursal -se toma la
    del punto de venta del turno abierto del usuario, y si no tiene
    ninguno abierto, no puede continuar-. Si por asignación a varias
    cajas llegara a tener más de un turno abierto a la vez, se toma el
    más reciente -hoy en la práctica solo se opera una caja por
    sucursal-.

    `solo_cobro=True` para todo lo que cobra (venta directa o conversión
    de cotización/pedido): un turno de mostrador (punto de venta tipo
    Pedido) no sirve para eso, solo para cotizar y levantar pedidos."""
    turnos = Turno.objects.filter(usuario=usuario, estatus=Turno.Estatus.ABIERTO)
    if solo_cobro:
        turnos = turnos.filter(punto_venta__tipo=PuntoVenta.Tipo.COBRO)
    return turnos.select_related("punto_venta", "punto_venta__almacen").first()


def abrir_turno(punto_venta, usuario, observaciones=""):
    """Abre un nuevo turno para ese punto de venta (caja o mostrador; qué
    tipo le corresponde a cada usuario lo valida la vista, ver
    tipos_punto_venta_de).
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
