from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cobros.services import generar_cuenta_por_cobrar
from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.scoping import almacenes_visibles
from apps.pedidos.forms import BuscarFolioPedidoForm
from apps.pedidos.models import Pedido
from apps.pedidos.services import convertir_pedido_a_venta
from apps.products.services import turno_abierto_de
from apps.ventas.forms import VentaForm
from apps.ventas.models import Venta
from apps.ventas.services import validar_efectivo_recibido, validar_venta_a_credito


def _pedidos_visibles(user):
    queryset = Pedido.objects.select_related("cliente", "almacen", "venta")
    visibles = almacenes_visibles(user)
    if visibles is not None:
        queryset = queryset.filter(almacen__in=visibles)
    return queryset


@permission_required("ventas.add_venta", raise_exception=True)
def buscar_pedido_view(request):
    """Punto de entrada para caja: captura el folio que trae el cliente de
    mostrador y lo lleva a la pantalla de conversión."""
    form = BuscarFolioPedidoForm(request.GET or None)

    if request.GET and form.is_valid():
        folio = form.cleaned_data["folio"].strip()
        pedido = _pedidos_visibles(request.user).filter(
            Q(numero_documento__iexact=folio) | Q(folio__iexact=folio)
        ).first()
        if pedido is None:
            form.add_error("folio", f"No se encontró ningún pedido con el folio '{folio}'.")
        else:
            return redirect("pedidos:pedido-convertir", pk=pedido.pk)

    return render(request, "pedidos/buscar_folio.html", {"form": form, "active_module": "orders"})


@permission_required("ventas.add_venta", raise_exception=True)
def convertir_pedido_view(request, pk):
    """Caja cobra el pedido TAL CUAL -mismos productos y cantidades, sin
    poder agregar ni quitar líneas: si algo cambia, se cancela y se levanta
    otro-. Solo elige forma de pago (y puede cambiar el cliente, por ejemplo
    para una venta a crédito o con factura). La mercancía ya estaba apartada
    desde que mostrador levantó el pedido, así que aquí no se vuelve a
    validar existencia."""
    pedido = get_object_or_404(_pedidos_visibles(request.user), pk=pk)

    # Doble clic o recarga de una conversión que ya se guardó: a la venta
    # creada, sin volver a validar (ver apps.core.envio_unico).
    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    if pedido.estatus != Pedido.Estatus.ABIERTO:
        return render(request, "pedidos/ya_cerrado.html", {"pedido": pedido, "active_module": "orders"})

    detalles = list(pedido.detalles.select_related("producto"))
    if not detalles:
        messages.error(request, "Este pedido no tiene productos; no se puede convertir.")
        return redirect("pedidos:pedido-list")

    # Igual que al convertir una cotización: el turno de quien cobra debe
    # ser de la MISMA sucursal del pedido -ahí está apartada la mercancía-.
    turno = turno_abierto_de(request.user, solo_cobro=True)
    if turno is None:
        messages.error(request, "No tienes un turno abierto en una caja. Ábrelo antes de convertir el pedido en venta.")
        return redirect("products:turno-list")
    if turno.punto_venta.almacen_id != pedido.almacen_id:
        messages.error(
            request,
            f'Tu turno está en "{turno.punto_venta.almacen.nombre}"; este pedido es de '
            f'"{pedido.almacen.nombre}". Conviértelo desde un turno abierto en esa sucursal.',
        )
        return redirect("pedidos:pedido-list")

    if request.method == "POST":
        form = VentaForm(request.POST)
        if form.is_valid():
            if not form.cleaned_data.get("forma_pago"):
                # Esta pantalla no ofrece dividir el cobro (igual que la
                # conversión de cotización): aquí la forma de pago es
                # obligatoria.
                form.add_error("forma_pago", "Indica la forma de pago.")
            else:
                form.instance.almacen = pedido.almacen
                form.instance.turno = turno
                try:
                    with transaction.atomic():
                        envio = reservar_envio(request)
                        venta = form.save()
                        convertir_pedido_a_venta(pedido, venta)
                        validar_efectivo_recibido(venta)
                        error_credito = validar_venta_a_credito(venta.cliente, venta.forma_pago, venta.total)
                        if error_credito:
                            raise ValueError(error_credito)
                        if venta.forma_pago.clave == Venta.CLAVE_CREDITO:
                            generar_cuenta_por_cobrar(venta)
                        envio.completar(reverse("ventas:venta-list"))
                except EnvioDuplicado as duplicado:
                    return respuesta_envio_duplicado(request, duplicado.url_resultado, "ventas:venta-list")
                except ERRORES_DE_NEGOCIO as e:
                    for mensaje in mensajes_de_error(e):
                        form.add_error(None, mensaje)
                else:
                    messages.success(
                        request,
                        f"Pedido {pedido.numero_documento} convertido a la venta {venta.folio}.",
                    )
                    return redirect("ventas:venta-list")
    else:
        form = VentaForm(
            initial={
                "cliente": pedido.cliente_id,
                "observaciones": (
                    f"Generada desde pedido {pedido.numero_documento}."
                    + (f" {pedido.observaciones}" if pedido.observaciones else "")
                ),
            },
        )

    return render(
        request,
        "pedidos/convertir_form.html",
        {
            "pedido": pedido,
            "detalles": detalles,
            "form": form,
            "turno": turno,
            "almacen": pedido.almacen,
            "active_module": "orders",
        },
    )
