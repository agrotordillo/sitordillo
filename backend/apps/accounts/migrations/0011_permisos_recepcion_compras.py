from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Compras recibe el producto contra la factura/nota del proveedor (Almacén
# ya podía hacerlo desde 0003_grupos_de_capacidades); si hay una incidencia
# en la recepción física, se reporta a Compras para el procedimiento
# correspondiente. Sin este permiso, "Compras - Completo" veía el botón
# "Recibir" en la orden de compra pero recibía un 403 al usarlo.
GRUPOS = ["Compras - Completo"]
PERMISOS = [
    ("lote", ["add"]),
]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("inventario"), verbosity=0)

    permisos = []
    for modelo, acciones in PERMISOS:
        content_type = ContentType.objects.get(app_label="inventario", model=modelo)
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
        content_type = ContentType.objects.get(app_label="inventario", model=modelo)
        for accion in acciones:
            permisos.append(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))

    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_permisos_stock_sucursal"),
        ("inventario", "0001_lote_movimiento_initial"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
