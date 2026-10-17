from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# El cajero (grupo "Ventas y Caja") ya generaba el borrador de una
# Factura individual (view+add, ver 0013_permisos_facturacion_ventas_caja)
# pero dependía de "Facturación" para completar el timbrado. El usuario
# confirmó que caja SÍ debe poder timbrar su propia factura -lo único
# que sigue fuera de su alcance es cancelar una ya timbrada
# (delete_factura), que sigue siendo exclusivo de Facturación/Administrador.
GRUPOS = ["Ventas y Caja"]
PERMISOS = ["change_factura"]


def _permisos(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="facturacion", model="factura")
    return [Permission.objects.get(content_type=content_type, codename=c) for c in PERMISOS]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("facturacion"), verbosity=0)
    permisos = _permisos(apps)
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.add(*permisos)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    permisos = _permisos(apps)
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.remove(*permisos)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_restriccion_una_principal"),
        ("facturacion", "0005_timbrado_seguro"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
