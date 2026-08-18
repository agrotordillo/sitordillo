from django.contrib import messages
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from apps.cotizaciones.forms import BuscarFolioForm
from apps.cotizaciones.models import Cotizacion
from apps.ventas.forms import VentaDetalleForm, VentaDetalleFormSet, VentaForm
from apps.ventas.models import Venta, VentaDetalle
from apps.ventas.services import procesar_lineas_venta, validar_stock_disponible


def buscar_cotizacion_view(request):
    """Punto de entrada para caja: captura el folio que trae el cliente y
    lo lleva a la pantalla de conversión (o de aviso, si ya fue usado)."""
    form = BuscarFolioForm(request.GET or None)

    if request.GET and form.is_valid():
        folio = form.cleaned_data["folio"].strip()
        cotizacion = Cotizacion.objects.filter(folio__iexact=folio).first()
        if cotizacion is None:
            form.add_error("folio", f"No se encontró ninguna cotización con el folio '{folio}'.")
        else:
            return redirect("cotizaciones:cotizacion-convertir", pk=cotizacion.pk)

    return render(request, "cotizaciones/buscar_folio.html", {"form": form, "active_module": "quotes"})


def convertir_cotizacion_view(request, pk):
    """Caja revisa/edita los datos traídos de la cotización y confirma la
    venta. El inventario solo se descuenta hasta aquí, nunca al generar la
    cotización en mostrador."""
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related("cliente", "almacen", "venta"), pk=pk
    )

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
        form = VentaForm(request.POST)
        formset = VentaDetalleFormSet(request.POST, instance=Venta(), prefix="detalles")
        if form.is_valid() and formset.is_valid():
            almacen = form.cleaned_data["almacen"]
            lineas = [
                (cd["producto"], cd["cantidad"], cd["estrategia_salida"])
                for f in formset
                if (cd := f.cleaned_data) and cd.get("producto") and not cd.get("DELETE")
            ]
            if not lineas:
                form.add_error(None, "Agrega al menos un producto a la venta.")
            else:
                errores_stock = validar_stock_disponible(almacen, lineas)
                for error in errores_stock:
                    form.add_error(None, error)

                if not errores_stock:
                    with transaction.atomic():
                        venta = form.save()
                        formset.instance = venta
                        formset.save()
                        procesar_lineas_venta(venta)
                        cotizacion.venta = venta
                        cotizacion.estatus = Cotizacion.Estatus.CONVERTIDA
                        cotizacion.save(update_fields=["venta", "estatus", "updated_at"])

                    messages.success(
                        request,
                        f"Cotización {cotizacion.folio} convertida a la venta {venta.folio}.",
                    )
                    return redirect("ventas:venta-list")
    else:
        form = VentaForm(initial={
            "cliente": cotizacion.cliente_id,
            "almacen": cotizacion.almacen_id,
            "observaciones": (
                f"Generada desde cotización {cotizacion.folio}."
                + (f" {cotizacion.observaciones}" if cotizacion.observaciones else "")
            ),
        })
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

    return render(
        request,
        "cotizaciones/convertir_form.html",
        {"cotizacion": cotizacion, "form": form, "formset": formset, "active_module": "quotes"},
    )
