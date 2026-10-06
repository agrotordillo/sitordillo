from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Los movimientos manuales de almacén (ajustes, sobrante, faltante, merma,
# regalía, devoluciones a/del proveedor, consumo de la empresa, devolución
# en móvil) alteran existencias sin una venta, compra o traspaso detrás,
# así que solo los registra el área de Compras -o el Administrador, que es
# superusuario y no necesita grupo-. Almacén y sucursales no los capturan.
# "change" es lo que permite editar el borrador, aplicarlo y cancelarlo.
GRUPOS = ["Compras - Captura", "Compras - Completo"]
ACCIONES = ["view", "add", "change"]


def _permisos(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="inventario", model="movimientoalmacen")
    return [Permission.objects.get(content_type=content_type, codename=f"{a}_movimientoalmacen") for a in ACCIONES]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("inventario"), verbosity=0)
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.add(*_permisos(apps))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre_grupo in GRUPOS:
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.remove(*_permisos(apps))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_permisos_factura_global"),
        ("inventario", "0009_movimiento_almacen"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
