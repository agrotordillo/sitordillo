from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# ProductoStockSucursal (apps.products) es un modelo nuevo posterior a la
# Fase 2 (0003_grupos_de_capacidades) - igual que Turno y Conversion antes,
# hay que asignarle sus permisos explícitamente. "Almacén" lo captura y
# vigila; "Compras - Completo" solo lo consulta como referencia al decidir
# qué comprar.
PERMISOS_POR_GRUPO = {
    "Almacén": ["view", "add", "change"],
    "Compras - Completo": ["view"],
}
MODELO = "productostocksucursal"


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    create_permissions(global_apps.get_app_config("products"), verbosity=0)
    content_type = ContentType.objects.get(app_label="products", model=MODELO)

    for nombre_grupo, acciones in PERMISOS_POR_GRUPO.items():
        grupo = Group.objects.get(name=nombre_grupo)
        for accion in acciones:
            permiso = Permission.objects.get(content_type=content_type, codename=f"{accion}_{MODELO}")
            grupo.permissions.add(permiso)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    content_type = ContentType.objects.get(app_label="products", model=MODELO)
    for nombre_grupo, acciones in PERMISOS_POR_GRUPO.items():
        grupo = Group.objects.get(name=nombre_grupo)
        for accion in acciones:
            permiso = Permission.objects.get(content_type=content_type, codename=f"{accion}_{MODELO}")
            grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_permisos_cobros"),
        ("products", "0021_productostocksucursal"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
