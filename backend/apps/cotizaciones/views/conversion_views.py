from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cobros.services import generar_cuenta_por_cobrar
from apps.core.envio_unico import EnvioDuplicado, envio_ya_procesado, reservar_envio, respuesta_envio_duplicado
from apps.core.errores import ERRORES_DE_NEGOCIO, mensajes_de_error
from apps.core.scoping import almacenes_visibles
from apps.cotizaciones.forms import BuscarFolioForm
from apps.cotizaciones.models import Cotizacion
from apps.products.services import fijar_precios_autorizados, turno_abierto_de
from apps.ventas.forms import VentaDetalleForm, VentaDetalleFormSet, VentaForm
from apps.ventas.models import Venta, VentaDetalle
from apps.ventas.services import (
    procesar_lineas_venta,
    validar_efectivo_recibido,
    validar_stock_disponible,
    validar_venta_a_credito,
)


class CotizacionYaConvertida(Exception):
    """Otra conversión de la misma cotización se confirmó primero."""


@permission_required("cotizaciones.view_cotizacion", raise_exception=True)
def buscar_cotizacion_view(request):
    """Punto de entrada para caja: captura el folio que trae el cliente y
    lo lleva a la pantalla de conversión (o de aviso, si ya fue usado)."""
    form = BuscarFolioForm(request.GET or None)

    if request.GET and form.is_valid():
        folio = form.cleaned_data["folio"].strip()
        cotizaciones_qs = Cotizacion.objects.all()
        visibles = almacenes_visibles(request.user)
        if visibles is not None:
            cotizaciones_qs = cotizaciones_qs.filter(almacen__in=visibles)
        cotizacion = cotizaciones_qs.filter(
            Q(numero_documento__iexact=folio) | Q(folio__iexact=folio)
        ).first()
        if cotizacion is None:
            form.add_error("folio", f"No se encontró ninguna cotización con el folio '{folio}'.")
        else:
            return redirect("cotizaciones:cotizacion-convertir", pk=cotizacion.pk)

    return render(request, "cotizaciones/buscar_folio.html", {"form": form, "active_module": "quotes"})


@permission_required("ventas.add_venta", raise_exception=True)
def convertir_cotizacion_view(request, pk):
    """Caja revisa/edita los datos traídos de la cotización y confirma la
    venta. El inventario solo se descuenta hasta aquí, nunca al generar la
    cotización en mostrador."""
    cotizaciones_qs = Cotizacion.objects.select_related("cliente", "almacen", "venta")
    visibles = almacenes_visibles(request.user)
    if visibles is not None:
        cotizaciones_qs = cotizaciones_qs.filter(almacen__in=visibles)
    cotizacion = get_object_or_404(cotizaciones_qs, pk=pk)

    # Doble clic o recarga de una conversión que ya se guardó: a la venta
    # creada, sin volver a validar (ver apps.core.envio_unico).
    if request.method == "POST" and (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)

    if cotizacion.estatus == Cotizacion.Estatus.CONVERTIDA:
        return render(
            request,
            "cotizaciones/ya_convertida.html",
            {"cotizacion": cotizacion, "active_module": "quotes"},
        )

    detalles = list(cotizacion.detalles.select_related("producto"))
    if not detalles:
        messages.error(request, "Esta cotización no tiene productos; no se puede convertir.")
        return redirect("cotizaciones:cotizacion-list")

    # Igual que en Crear venta: la sucursal ya no la elige caja, se toma
    # de su turno propio y abierto -pero aquí, a diferencia de una venta
    # directa, esa sucursal debe ser la MISMA de la cotización (el precio
    # y el stock ya se cotizaron contra ese almacén; convertirla desde
    # otra sucursal decontaría el inventario equivocado).
    turno = turno_abierto_de(request.user, solo_cobro=True)
    if turno is None:
        messages.error(request, "No tienes un turno abierto en una caja. Ábrelo antes de convertir la cotización en venta.")
        return redirect("products:turno-list")
    if turno.punto_venta.almacen_id != cotizacion.almacen_id:
        messages.error(
            request,
            f'Tu turno está en "{turno.punto_venta.almacen.nombre}"; esta cotización es de '
            f'"{cotizacion.almacen.nombre}". Conviértela desde un turno abierto en esa sucursal.',
        )
        return redirect("cotizaciones:cotizacion-list")
    almacen = cotizacion.almacen

    if request.method == "POST":
        form = VentaForm(request.POST)
        formset = VentaDetalleFormSet(request.POST, instance=Venta(), prefix="detalles")
        if form.is_valid() and formset.is_valid():
            form.instance.almacen = almacen
            form.instance.turno = turno

            # El precio no lo decide quien está en caja, ni siquiera al
            # convertir una cotización ya cotizada -se vuelve a resolver
            # aquí con el cliente y la sucursal de la venta, nunca se
            # copia el precio_unitario que trae el formset precargado
            # desde la cotización-.
            fijar_precios_autorizados(
                formset, form.cleaned_data.get("cliente"), almacen, VentaDetalle.Estrategia.FIFO,
            )

            lineas = [
                (cd["producto"], cd["cantidad"], VentaDetalle.Estrategia.FIFO)
                for f in formset
                if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
            ]

            if not form.cleaned_data.get("forma_pago"):
                # VentaForm.forma_pago ya no es obligatorio a nivel de
                # formulario -se puede dejar vacío cuando se divide el
                # cobro (ver VentaCreateView)-, pero esta pantalla no
                # ofrece esa opción: aquí sigue siendo obligatorio elegir
                # una sola forma de pago.
                form.add_error("forma_pago", "Indica la forma de pago.")
            elif not lineas:
                form.add_error(None, "Agrega al menos un producto a la venta.")
            else:
                errores_stock = validar_stock_disponible(almacen, lineas)
                for error in errores_stock:
                    form.add_error(None, error)

                if not errores_stock:
                    try:
                        with transaction.atomic():
                            envio = reservar_envio(request)
                            # Con la fila bloqueada: dos cajas (o un doble
                            # clic) convirtiendo la misma cotización a la vez
                            # no deben generar dos ventas (B15 en
                            # docs/AUDITORIA.md). La segunda espera aquí a la
                            # primera y después la encuentra ya convertida.
                            cotizacion = Cotizacion.objects.select_for_update().get(pk=cotizacion.pk)
                            if cotizacion.estatus == Cotizacion.Estatus.CONVERTIDA:
                                raise CotizacionYaConvertida
                            venta = form.save()
                            formset.instance = venta
                            formset.save()
                            validar_efectivo_recibido(venta)
                            error_credito = validar_venta_a_credito(
                                venta.cliente, venta.forma_pago, venta.total
                            )
                            if error_credito:
                                raise ValueError(error_credito)
                            procesar_lineas_venta(venta)
                            if venta.forma_pago and venta.forma_pago.clave == Venta.CLAVE_CREDITO:
                                generar_cuenta_por_cobrar(venta)
                            cotizacion.venta = venta
                            cotizacion.estatus = Cotizacion.Estatus.CONVERTIDA
                            cotizacion.save(update_fields=["venta", "estatus", "updated_at", "updated_by"])
                            envio.completar(reverse("ventas:venta-list"))
                    except EnvioDuplicado as duplicado:
                        return respuesta_envio_duplicado(request, duplicado.url_resultado, "ventas:venta-list")
                    except CotizacionYaConvertida:
                        return render(
                            request,
                            "cotizaciones/ya_convertida.html",
                            {"cotizacion": Cotizacion.objects.get(pk=cotizacion.pk), "active_module": "quotes"},
                        )
                    except ERRORES_DE_NEGOCIO as e:
                        for mensaje in mensajes_de_error(e):
                            form.add_error(None, mensaje)
                    else:
                        messages.success(
                            request,
                            f"Cotización {cotizacion.numero_documento} convertida a la venta {venta.folio}.",
                        )
                        return redirect("ventas:venta-list")
    else:
        form = VentaForm(
            initial={
                "cliente": cotizacion.cliente_id,
                "observaciones": (
                    f"Generada desde cotización {cotizacion.numero_documento}."
                    + (f" {cotizacion.observaciones}" if cotizacion.observaciones else "")
                ),
            },
        )
        initial_detalles = [
            # precio_unitario se precarga solo para que la pantalla muestre
            # algo antes de guardar (lo que se cotizó); al confirmar la
            # venta, fijar_precios_autorizados() lo vuelve a resolver de
            # cero y este valor precargado se descarta.
            {
                "producto": d.producto_id,
                "cantidad": d.cantidad,
                "precio_unitario": d.precio_unitario,
            }
            for d in detalles
        ]
        # Un formset sin datos ("unbound") solo dibuja `extra` filas en
        # blanco; para precargar todas las líneas de la cotización hay que
        # fijar `extra` al número real de líneas (solo aplica al GET: en el
        # POST el número de filas ya lo trae el management form).
        PrefillFormSet = inlineformset_factory(
            Venta, VentaDetalle, form=VentaDetalleForm, extra=len(initial_detalles), can_delete=True,
        )
        formset = PrefillFormSet(instance=Venta(), initial=initial_detalles, prefix="detalles")

    return render(
        request,
        "cotizaciones/convertir_form.html",
        {
            "cotizacion": cotizacion,
            "form": form,
            "formset": formset,
            "turno": turno,
            "almacen": almacen,
            "active_module": "quotes",
        },
    )
