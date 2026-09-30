from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from apps.cobros.services import generar_cuenta_por_cobrar
from apps.core.scoping import almacenes_visibles
from apps.cotizaciones.forms import BuscarFolioForm
from apps.cotizaciones.models import Cotizacion
from apps.products.services import fijar_precios_autorizados, turno_abierto_de
from apps.ventas.forms import VentaDetalleForm, VentaDetalleFormSet, VentaForm
from apps.ventas.models import Venta, VentaDetalle
from apps.ventas.services import (
    procesar_lineas_venta,
    validar_stock_disponible,
    validar_venta_a_credito,
)


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
    turno = turno_abierto_de(request.user)
    if turno is None:
        messages.error(request, "No tienes un turno abierto. Ábrelo antes de convertir la cotización en venta.")
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
                            venta = form.save()
                            formset.instance = venta
                            formset.save()
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
                            cotizacion.save(update_fields=["venta", "estatus", "updated_at"])
                    except ValueError as e:
                        form.add_error(None, str(e))
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
