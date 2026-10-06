from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Mostrador abre su propio turno en un punto de venta tipo Pedido (un
# mostrador, nunca una caja: ver products.services.tipos_punto_venta_de) y
# con él levanta cotizaciones y pedidos. Hasta ahora este rol no tenía
# ningún permiso de Turno, así que no podía abrirlo y por lo tanto
# tampoco cotizar ni levantar pedidos. Se da desde el rol para que el
# Administrador lo controle asignando o quitando el grupo en la
# administración de usuarios.
GRUPO = "Mostrador y Cotización"
PERMISOS = ["view_turno", "add_turno", "change_turno"]


def _permisos(apps):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="products", model="turno")
    return [Permission.objects.get(content_type=content_type, codename=c) for c in PERMISOS]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("products"), verbosity=0)
    grupo = Group.objects.filter(name=GRUPO).first()
    if grupo is not None:
        grupo.permissions.add(*_permisos(apps))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    grupo = Group.objects.filter(name=GRUPO).first()
    if grupo is not None:
        grupo.permissions.remove(*_permisos(apps))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_permisos_pedidos"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
