from django.db import migrations
from django.utils.text import slugify

CLAVE = "17"
DESCRIPCION_NUEVA = "Nota de crédito"
DESCRIPCION_ANTERIOR = "Compensación"


def _actualizar(apps, schema_editor, descripcion):
    FormaPago = apps.get_model("fiscal", "FormaPago")
    FormaPago.objects.filter(clave=CLAVE).update(
        descripcion=descripcion,
        slug=slugify(f"{CLAVE}-{descripcion}"),
    )


def renombrar(apps, schema_editor):
    # La clave SAT 17 es oficialmente "Compensación", pero en la operación
    # del negocio siempre se usa para registrar una nota de crédito del
    # proveedor (ver apps.pagos.models.Pago.CLAVE_COMPENSACION), así que se
    # renombra la etiqueta visible para que coincida con cómo se usa.
    _actualizar(apps, schema_editor, DESCRIPCION_NUEVA)


def revertir(apps, schema_editor):
    _actualizar(apps, schema_editor, DESCRIPCION_ANTERIOR)


class Migration(migrations.Migration):

    dependencies = [
        ("fiscal", "0008_retarget_user_fk_to_accounts"),
    ]

    operations = [
        migrations.RunPython(renombrar, revertir),
    ]
