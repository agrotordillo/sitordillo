from django.db import migrations

# A diferencia de "Mostrador y Cotización" (que solo busca clientes ya
# registrados, ver 0014_quitar_add_cliente_mostrador), "Ventas y Caja" sí
# necesita poder registrar Y actualizar un cliente -lo pide el tema de
# facturación: capturar o corregir sus datos fiscales (RFC, régimen,
# etc.) al momento de facturar la venta-. 0003_grupos_de_capacidades ya
# le daba "add"; aquí se le agrega "change" para completar el flujo.
# Crédito, descuento y precio preferente (lista_precio) siguen siendo
# exclusivos del Administrador aunque el cajero edite un cliente -esos
# campos ni aparecen en el formulario para quien no es superusuario, ver
# apps.clientes.forms.ClienteForm-.
GRUPO = "Ventas y Caja"
CODENAME = "change_cliente"


def agregar_permiso(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="clientes", model="cliente")
    permiso = Permission.objects.get(content_type=content_type, codename=CODENAME)
    grupo.permissions.add(permiso)


def quitar_permiso(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="clientes", model="cliente")
    permiso = Permission.objects.get(content_type=content_type, codename=CODENAME)
    grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_quitar_add_cliente_mostrador"),
    ]

    operations = [
        migrations.RunPython(agregar_permiso, quitar_permiso),
    ]
