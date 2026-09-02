from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Conversion es un modelo nuevo (posterior a la Fase 2, ver
# 0003_grupos_de_capacidades): a Django no le basta con crear sus permisos,
# hay que asignarlos al grupo que corresponde explícitamente. Es una
# actividad propia de Almacén (ver conversación de diseño de
# apps.inventario.Conversion) - view+add, sin change: una conversión ya
# hecha no se edita, se registra otra si hubo un error.
# RecetaConversion (el catálogo de equivalencias) se deja fuera de todos los
# grupos a propósito: es configuración estructural, igual que CentroCosto o
# los catálogos de products, gestionada por el Administrador.
GRUPO = "Almacén"
PERMISOS = ["view_conversion", "add_conversion"]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("inventario"), verbosity=0)

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="inventario", model="conversion")
    for codename in PERMISOS:
        grupo.permissions.add(Permission.objects.get(content_type=content_type, codename=codename))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="inventario", model="conversion")
    for codename in PERMISOS:
        grupo.permissions.remove(Permission.objects.get(content_type=content_type, codename=codename))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_facturacion_change_factura"),
        ("inventario", "0005_recetaconversion_conversion_and_more"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
