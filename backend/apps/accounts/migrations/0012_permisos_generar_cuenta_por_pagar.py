from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# generar_cuenta_por_pagar (apps.pagos.services) es el botón manual en
# Compras para generar la cuenta por pagar de una orden ya recibida (ver
# apps.pagos.views.cuenta_views.generar_cuenta_view). 0003_grupos_de_
# capacidades solo le dio "view" de CuentaPorPagar a "Compras - Completo",
# así que el botón aparecía pero daba 403 al usarlo.
GRUPOS = ["Compras - Completo"]
PERMISOS = [
    ("cuentaporpagar", ["add"]),
]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("pagos"), verbosity=0)

    permisos = []
    for modelo, acciones in PERMISOS:
        content_type = ContentType.objects.get(app_label="pagos", model=modelo)
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
        content_type = ContentType.objects.get(app_label="pagos", model=modelo)
        for accion in acciones:
            permisos.append(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))

    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_permisos_recepcion_compras"),
        ("pagos", "0001_cuenta_por_pagar_pago_initial"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
