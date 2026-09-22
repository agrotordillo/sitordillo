from django.db import migrations, models


def poblar_numeros(apps, schema_editor):
    Almacen = apps.get_model("products", "Almacen")
    PuntoVenta = apps.get_model("products", "PuntoVenta")

    for numero, almacen in enumerate(Almacen.objects.order_by("pk"), start=1):
        almacen.numero = numero
        almacen.save(update_fields=["numero"])

    for almacen in Almacen.objects.order_by("pk"):
        puntos = PuntoVenta.objects.filter(almacen=almacen).order_by("pk")
        for numero, punto_venta in enumerate(puntos, start=1):
            punto_venta.numero = numero
            punto_venta.save(update_fields=["numero"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0026_alter_producto_precio_costo"),
    ]

    operations = [
        migrations.AddField(
            model_name="almacen",
            name="numero",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                unique=True,
                verbose_name="Número de almacén",
                help_text="Los 2 dígitos que identifican a este almacén en los folios de mostrador (cotizaciones, ventas).",
            ),
        ),
        migrations.AddField(
            model_name="puntoventa",
            name="numero",
            field=models.PositiveSmallIntegerField(
                null=True,
                blank=True,
                verbose_name="Número de punto de venta",
                help_text="Los 2 dígitos que, junto con el número de almacén, identifican a este punto de venta en los folios de mostrador.",
            ),
        ),
        migrations.AddField(
            model_name="puntoventa",
            name="consecutivo_cotizacion",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                verbose_name="Último consecutivo de cotización usado",
            ),
        ),
        migrations.RunPython(poblar_numeros, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="almacen",
            name="numero",
            field=models.PositiveSmallIntegerField(
                unique=True,
                verbose_name="Número de almacén",
                help_text="Los 2 dígitos que identifican a este almacén en los folios de mostrador (cotizaciones, ventas).",
            ),
        ),
        migrations.AlterField(
            model_name="puntoventa",
            name="numero",
            field=models.PositiveSmallIntegerField(
                verbose_name="Número de punto de venta",
                help_text="Los 2 dígitos que, junto con el número de almacén, identifican a este punto de venta en los folios de mostrador.",
            ),
        ),
        migrations.AddConstraint(
            model_name="puntoventa",
            constraint=models.UniqueConstraint(fields=["almacen", "numero"], name="unico_numero_por_almacen"),
        ),
    ]
