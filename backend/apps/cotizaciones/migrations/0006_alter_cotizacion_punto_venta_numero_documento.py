import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cotizaciones", "0005_poblar_punto_venta_numero_documento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cotizacion",
            name="punto_venta",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cotizaciones",
                to="products.puntoventa",
                verbose_name="Punto de venta",
            ),
        ),
        migrations.AlterField(
            model_name="cotizacion",
            name="numero_documento",
            field=models.CharField(
                max_length=20,
                unique=True,
                editable=False,
                verbose_name="Número de cotización",
                help_text="Folio para el cliente: número de almacén + número de punto de venta + consecutivo. Se genera solo al guardar y no se puede editar.",
            ),
        ),
        migrations.AddIndex(
            model_name="cotizacion",
            index=models.Index(fields=["punto_venta"], name="cotizaciones_punto_venta_idx"),
        ),
    ]
