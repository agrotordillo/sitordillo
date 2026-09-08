# Segunda mitad de 0019_turno_punto_venta: con la columna ya llena de
# datos (en su propia migración/transacción), aquí se hace obligatoria,
# se quita "almacen" y se mueve el índice y la restricción única de
# "un turno abierto" de almacen a punto_venta.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0019_turno_punto_venta"),
    ]

    operations = [
        migrations.AlterField(
            model_name="turno",
            name="punto_venta",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="turnos",
                to="products.puntoventa",
                verbose_name="Punto de venta",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="turno",
            name="trn_un_turno_abierto_por_almacen",
        ),
        migrations.RemoveIndex(
            model_name="turno",
            name="products_tu_almacen_3528e5_idx",
        ),
        migrations.RemoveField(
            model_name="turno",
            name="almacen",
        ),
        migrations.AddIndex(
            model_name="turno",
            index=models.Index(fields=["punto_venta"], name="products_tu_punto_v_2cf579_idx"),
        ),
        migrations.AddConstraint(
            model_name="turno",
            constraint=models.UniqueConstraint(
                condition=models.Q(("estatus", "abierto")),
                fields=("punto_venta",),
                name="trn_un_turno_abierto_por_punto_venta",
            ),
        ),
    ]
