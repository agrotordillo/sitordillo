import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0027_almacen_puntoventa_numero"),
        ("cotizaciones", "0003_cotizaciondetalle_lista_precio"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotizacion",
            name="punto_venta",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cotizaciones",
                to="products.puntoventa",
                verbose_name="Punto de venta",
            ),
        ),
        migrations.AddField(
            model_name="cotizacion",
            name="numero_documento",
            field=models.CharField(
                max_length=20,
                null=True,
                blank=True,
                unique=True,
                editable=False,
                verbose_name="Número de cotización",
                help_text="Folio para el cliente: número de almacén + número de punto de venta + consecutivo. Se genera solo al guardar y no se puede editar.",
            ),
        ),
    ]
