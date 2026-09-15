from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# La cajera (grupo "Ventas y Caja") atiende la venta de principio a fin en
# las sucursales chicas y debe poder generar la factura de su propia venta
# en el momento, sin depender de que alguien del grupo "Facturación" lo
# haga después. Se le concede el mismo alcance base que ya tiene ese
# grupo -view+add, sin "change" (completar el timbrado) ni "delete"
# (cancelar CFDI), que siguen siendo de Facturación/Administrador
# respectivamente-.
GRUPOS = ["Ventas y Caja"]
PERMISOS = [
    ("factura", ["view", "add"]),
]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("facturacion"), verbosity=0)

    permisos = []
    for modelo, acciones in PERMISOS:
        content_type = ContentType.objects.get(app_label="facturacion", model=modelo)
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
        content_type = ContentType.objects.get(app_label="facturacion", model=modelo)
        for accion in acciones:
            permisos.append(Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}"))

    for nombre_grupo in GRUPOS:
        grupo = Group.objects.get(name=nombre_grupo)
        for permiso in permisos:
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_permisos_generar_cuenta_por_pagar"),
        ("facturacion", "0001_empresa_factura_initial"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
