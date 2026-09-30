import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Ya con todos los conceptos agrupados por la 0006, el grupo pasa a
    ser obligatorio."""

    dependencies = [
        ("gastos", "0006_catalogo_conceptos_centros_vehiculos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="categoriagasto",
            name="grupo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="conceptos",
                to="gastos.grupogasto",
                verbose_name="Grupo",
            ),
        ),
    ]
