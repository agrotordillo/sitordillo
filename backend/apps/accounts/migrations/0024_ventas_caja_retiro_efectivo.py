from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# El cajero (grupo "Ventas y Caja") registra los retiros de efectivo de su
# propio turno -por un gasto pagado con la caja o por mandar efectivo a la
# caja fuerte- sin autorización de nadie más, igual que en scvweb (ver
# ventas.RetiroEfectivo). No se le da change/delete: un retiro ya impreso
# no se edita ni se borra desde caja.
GRUPOS = ["Ventas y Caja"]
PERMISOS = ["view_retiroefectivo", "add_retiroefectivo"]


def _permisos(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="ventas", model="retiroefectivo")
    return [Permission.objects.get(content_type=content_type, codename=c) for c in PERMISOS]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("ventas"), verbosity=0)
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
        ("accounts", "0023_ventas_caja_timbra_factura"),
        ("ventas", "0011_retiro_efectivo"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
