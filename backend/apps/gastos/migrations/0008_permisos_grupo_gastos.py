from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# El grupo "Gastos" (accounts.0003) solo consulta los catálogos
# estructurales para elegirlos al registrar un gasto, igual que
# CentroCosto: los vehículos y los grupos de gasto los da de alta el
# Administrador.
PERMISOS = [("vehiculo", "view"), ("grupogasto", "view")]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.filter(name="Gastos").first()
    if grupo is None:
        return
    # En un migrate desde cero los permisos de los modelos nuevos todavía no
    # existen (los crea la señal post_migrate al final); ver accounts.0003.
    create_permissions(global_apps.get_app_config("gastos"), verbosity=0)
    for modelo, accion in PERMISOS:
        content_type = ContentType.objects.get(app_label="gastos", model=modelo)
        grupo.permissions.add(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo = Group.objects.filter(name="Gastos").first()
    if grupo is None:
        return
    codenames = [f"{accion}_{modelo}" for modelo, accion in PERMISOS]
    grupo.permissions.remove(*Permission.objects.filter(content_type__app_label="gastos", codename__in=codenames))


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0007_concepto_grupo_obligatorio"),
        ("accounts", "0003_grupos_de_capacidades"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
