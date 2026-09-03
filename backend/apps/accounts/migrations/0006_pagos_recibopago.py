from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# ReciboPago es un modelo nuevo (encabezado que agrupa los Pago de un mismo
# evento de pago, con su folio consecutivo - ver conversación de diseño de
# la pantalla "Pagos"), posterior a la Fase 2 (0003_grupos_de_capacidades):
# igual que con Conversion (ver 0005_almacen_conversion), hay que asignarle
# sus permisos al grupo "Pagos" explícitamente. Solo view+add: un recibo se
# genera junto con su(s) Pago(s) y no se edita directamente -lo que se
# corrige es el Pago ya registrado, vía pagos.change_pago (ya concedido).
GRUPO = "Pagos"
PERMISOS = ["view_recibopago", "add_recibopago"]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("pagos"), verbosity=0)

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="pagos", model="recibopago")
    for codename in PERMISOS:
        grupo.permissions.add(Permission.objects.get(content_type=content_type, codename=codename))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="pagos", model="recibopago")
    for codename in PERMISOS:
        grupo.permissions.remove(Permission.objects.get(content_type=content_type, codename=codename))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_almacen_conversion"),
        ("pagos", "0005_recibopago_pago_recibo_and_more"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
