import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Alinea los nombres del código con los de la pantalla: el catálogo
    `CategoriaGasto` pasa a `ConceptoGasto` (y `Gasto.categoria` a
    `Gasto.concepto_gasto`), y el texto libre del vale, que se llamaba
    `Gasto.concepto`, pasa a `Gasto.descripcion`. Se renombra primero
    `concepto` para no confundirlo con el campo nuevo."""

    dependencies = [
        ("gastos", "0008_permisos_grupo_gastos"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="gasto", name="gastos_gast_categor_1b564a_idx"),
        migrations.RenameField(model_name="gasto", old_name="concepto", new_name="descripcion"),
        migrations.RenameModel(old_name="CategoriaGasto", new_name="ConceptoGasto"),
        migrations.RenameField(model_name="gasto", old_name="categoria", new_name="concepto_gasto"),
        migrations.AddIndex(
            model_name="gasto",
            index=models.Index(fields=["concepto_gasto"], name="gastos_gast_concept_4db307_idx"),
        ),
        migrations.AlterField(
            model_name="gasto",
            name="descripcion",
            field=models.CharField(
                help_text='Lo que dice el vale (p. ej. "Pago de recibo de luz de Lerdo, bimestre 4").',
                max_length=255,
                verbose_name="Descripción del gasto",
            ),
        ),
        migrations.AlterField(
            model_name="gasto",
            name="centro_costo",
            field=models.ForeignKey(
                help_text="Quién generó/pagó el gasto. Si es compartido, aquí se registra el centro de origen (p. ej. "
                "Administración) y el detalle real por centro de costo va en la distribución.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="gastos",
                to="gastos.centrocosto",
                verbose_name="Centro de costo de origen",
            ),
        ),
        migrations.AddField(
            model_name="grupogasto",
            name="exclusivo_personal",
            field=models.BooleanField(
                default=False,
                help_text="Sus conceptos (p. ej. gastos médicos o colegiaturas de los dueños) no se pueden cargar a "
                "una sucursal, proyecto o unidad de negocio.",
                verbose_name="Solo para centros de costo de tipo Personal",
            ),
        ),
    ]
