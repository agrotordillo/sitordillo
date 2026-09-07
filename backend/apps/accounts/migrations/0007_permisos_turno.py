from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Turno (apertura/cierre de sucursal, ver products.Turno) es un modelo
# nuevo posterior a la Fase 2 (0003_grupos_de_capacidades) - igual que con
# Conversion (0005_almacen_conversion) y ReciboPago (0006_pagos_recibopago),
# hay que asignarle sus permisos explícitamente. Se concede a "Almacén"
# (quien opera la sucursal día a día) y a "Gastos" (quien necesita elegir
# o abrir un turno al registrar un gasto, ver Gasto.turno) - una misma
# persona en una sucursal chica suele estar en ambos grupos a la vez.
GRUPOS = ["Almacén", "Gastos"]
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
        ("accounts", "0006_pagos_recibopago"),
        ("products", "0018_turno"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
