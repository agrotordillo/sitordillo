from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from apps.cobros.services import generar_cuenta_por_cobrar
from apps.core.scoping import almacenes_visibles
from apps.cotizaciones.forms import BuscarFolioForm
from apps.cotizaciones.models import Cotizacion
from apps.products.models import Turno
from apps.ventas.forms import VentaDetalleForm, VentaDetalleFormSet, VentaForm
from apps.ventas.models import Venta, VentaDetalle
from apps.ventas.services import (
    procesar_lineas_venta,
    validar_stock_disponible,
    validar_turno_abierto,
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
        cotizacion = cotizaciones_qs.filter(folio__iexact=folio).first()
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

    if request.method == "POST":
        form = VentaForm(request.POST, user=request.user)
        formset = VentaDetalleFormSet(request.POST, instance=Venta(), prefix="detalles")
        if form.is_valid() and formset.is_valid():
            almacen = form.cleaned_data["almacen"]
            error_turno = validar_turno_abierto(almacen, request.user)
            lineas = [
                (cd["producto"], cd["cantidad"], cd["estrategia_salida"])
                for f in formset
                if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
            ]

            if error_turno:
                form.add_error(None, error_turno)
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
                            if venta.forma_pago.clave == Venta.CLAVE_CREDITO:
                                generar_cuenta_por_cobrar(venta)
                            cotizacion.venta = venta
                            cotizacion.estatus = Cotizacion.Estatus.CONVERTIDA
                            cotizacion.save(update_fields=["venta", "estatus", "updated_at"])
                    except ValueError as e:
                        form.add_error(None, str(e))
                    else:
                        messages.success(
                            request,
                            f"Cotización {cotizacion.folio} convertida a la venta {venta.folio}.",
                        )
                        return redirect("ventas:venta-list")
    else:
        form = VentaForm(
            initial={
                "cliente": cotizacion.cliente_id,
                "almacen": cotizacion.almacen_id,
                "observaciones": (
                    f"Generada desde cotización {cotizacion.folio}."
                    + (f" {cotizacion.observaciones}" if cotizacion.observaciones else "")
                ),
            },
            user=request.user,
        )
        initial_detalles = [
            {
                "producto": d.producto_id,
                "cantidad": d.cantidad,
                "precio_unitario": d.precio_unitario,
                "descuento": d.descuento,
                "estrategia_salida": d.estrategia_salida,
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

    # Mismo aviso previo que en Crear venta (ver VentaCreateView): en cuáles
    # de las sucursales que puede elegir el usuario actual NO tiene su
    # propio turno abierto -no bloquea ver la pantalla, solo informa antes
    # de llenar todo; el candado real está arriba, en validar_turno_abierto.
    almacenes = list(form.fields["almacen"].queryset)
    con_turno_propio_abierto = set(
        Turno.objects.filter(
            punto_venta__almacen__in=almacenes, usuario=request.user, estatus=Turno.Estatus.ABIERTO
        ).values_list("punto_venta__almacen_id", flat=True)
    )
    sucursales_sin_turno = [a for a in almacenes if a.pk not in con_turno_propio_abierto]

    return render(
        request,
        "cotizaciones/convertir_form.html",
        {
            "cotizacion": cotizacion,
            "form": form,
            "formset": formset,
            "sucursales_sin_turno": sucursales_sin_turno,
            "active_module": "quotes",
        },
    )
