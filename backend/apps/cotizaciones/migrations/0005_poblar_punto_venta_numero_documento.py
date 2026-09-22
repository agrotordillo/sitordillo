from django.db import migrations


def poblar_punto_venta_y_numero_documento(apps, schema_editor):
    Cotizacion = apps.get_model("cotizaciones", "Cotizacion")
    PuntoVenta = apps.get_model("products", "PuntoVenta")

    for cotizacion in Cotizacion.objects.order_by("pk"):
        punto_venta = PuntoVenta.objects.filter(almacen_id=cotizacion.almacen_id).order_by("pk").first()
        if punto_venta is None:
            raise RuntimeError(
                f"La cotización {cotizacion.pk} (almacén {cotizacion.almacen_id}) no tiene ningún "
                "punto de venta configurado; agrega uno antes de aplicar esta migración."
            )
        punto_venta.consecutivo_cotizacion += 1
        punto_venta.save(update_fields=["consecutivo_cotizacion"])
        almacen = punto_venta.almacen
        cotizacion.punto_venta = punto_venta
        cotizacion.numero_documento = (
            f"{almacen.numero:02d}{punto_venta.numero:02d}C{punto_venta.consecutivo_cotizacion:07d}"
        )
        cotizacion.save(update_fields=["punto_venta", "numero_documento"])


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0004_cotizacion_punto_venta_numero_documento"),
    ]

    operations = [
        migrations.RunPython(poblar_punto_venta_y_numero_documento, reverse_code=migrations.RunPython.noop),
    ]
