from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Cuentas por cobrar (apps.cobros) es un módulo nuevo posterior a la Fase 2
# (0003_grupos_de_capacidades) - igual que Conversion, ReciboPago y Turno
# antes, hay que asignarle sus permisos explícitamente. Se concede a
# "Ventas y Caja": son quienes venden a crédito (forma de pago 99) y
# quienes después cobran esas cuentas cuando el cliente regresa a pagar.
GRUPOS = ["Ventas y Caja"]
PERMISOS = [
    ("cuentaporcobrar", ["view", "add", "change"]),
    ("cobro", ["view", "add", "change"]),
]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("cobros"), verbosity=0)

    permisos = []
    for modelo, acciones in PERMISOS:
        content_type = ContentType.objects.get(app_label="cobros", model=modelo)
        for accion in acciones:
            permisos.append(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))

    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.add(permiso)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    permisos = []
    for modelo, acciones in PERMISOS:
        content_type = ContentType.objects.get(app_label="cobros", model=modelo)
        for accion in acciones:
            permisos.append(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))

    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_permisos_turno_ventas"),
        ("cobros", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
