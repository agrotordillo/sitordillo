from django.db import migrations
from django.utils.text import slugify

NOMBRE_PUBLICO_GENERAL = "Público en general"


def seed_cliente_publico_general(apps, schema_editor):
    Cliente = apps.get_model("clientes", "Cliente")
    Cliente.objects.update_or_create(
        nombre=NOMBRE_PUBLICO_GENERAL,
        defaults={
            "folio": "CLI-PUBLICO",
            "slug": slugify(NOMBRE_PUBLICO_GENERAL),
        },
    )


def unseed_cliente_publico_general(apps, schema_editor):
    Cliente = apps.get_model("clientes", "Cliente")
    Cliente.objects.filter(nombre=NOMBRE_PUBLICO_GENERAL).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0001_cliente_initial"),
    ]

    operations = [
        migrations.RunPython(seed_cliente_publico_general, unseed_cliente_publico_general),
    ]
