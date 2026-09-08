from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Con el candado de "no se puede vender sin turno abierto" (ver
# ventas.services.validar_turno_abierto), quien vende en mostrador/caja
# también necesita poder abrir y cerrar su propio turno -antes solo podían
# "Almacén" y "Gastos" (ver 0007_permisos_turno), pensado para quien opera
# la sucursal o registra gastos, no para el flujo de venta.
GRUPOS = ["Ventas y Caja"]
PERMISOS = ["view_turno", "add_turno", "change_turno"]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("products"), verbosity=0)

    content_type = ContentType.objects.get(app_label="products", model="turno")
    permisos = [Permission.objects.get(content_type=content_type, codename=codename) for codename in PERMISOS]
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.add(permiso)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type = ContentType.objects.get(app_label="products", model="turno")
    permisos = [Permission.objects.get(content_type=content_type, codename=codename) for codename in PERMISOS]
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_permisos_turno"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
