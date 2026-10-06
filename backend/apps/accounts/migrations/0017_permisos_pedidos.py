from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Pedido es un modelo nuevo (ver apps.pedidos). Mostrador levanta
# cotizaciones Y pedidos, y nada más: no recibe ningún permiso de ventas,
# así que no puede convertir un pedido en venta (eso exige
# ventas.add_venta, de "Ventas y Caja"). Caja solo los consulta para
# cobrarlos. Ambos pueden cancelar uno abierto (el cliente ya no lo quiso,
# en mostrador o al llegar a caja), lo que regresa la mercancía apartada
# al inventario.
GRUPOS_PERMISOS = {
    "Mostrador y Cotización": [
        ("pedido", ["view_pedido", "add_pedido", "change_pedido", "cancelar_pedido"]),
        ("pedidodetalle", ["view_pedidodetalle", "add_pedidodetalle", "change_pedidodetalle"]),
    ],
    "Ventas y Caja": [
        ("pedido", ["view_pedido", "cancelar_pedido"]),
        ("pedidodetalle", ["view_pedidodetalle"]),
    ],
}


def _permisos(apps, modelo, codenames):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="pedidos", model=modelo)
    return [Permission.objects.get(content_type=content_type, codename=c) for c in codenames]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("pedidos"), verbosity=0)

    for nombre_grupo, reglas in GRUPOS_PERMISOS.items():
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is None:
            continue
        for modelo, codenames in reglas:
            grupo.permissions.add(*_permisos(apps, modelo, codenames))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre_grupo, reglas in GRUPOS_PERMISOS.items():
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is None:
            continue
        for modelo, codenames in reglas:
            grupo.permissions.remove(*_permisos(apps, modelo, codenames))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0016_permisos_ensamble_paquete"),
        ("pedidos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
