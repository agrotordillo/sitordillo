from django.db import migrations

# "Mostrador y Cotización" solo debe poder BUSCAR clientes ya registrados
# al levantar una cotización, nunca darlos de alta ni editarlos desde ahí
# -el alta/edición de cliente (y su precio preferencial, ver
# Cliente.lista_precio, ya exclusivo del Administrador desde ClienteForm)
# es tarea de Administración-. 0003_grupos_de_capacidades le dio "view" y
# "add" de Cliente por error; se le quita "add" aquí (view se queda, para
# poder buscarlos).
GRUPO = "Mostrador y Cotización"
CODENAME = "add_cliente"


def quitar_permiso(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="clientes", model="cliente")
    permiso = Permission.objects.filter(content_type=content_type, codename=CODENAME).first()
    if permiso:
        grupo.permissions.remove(permiso)


def agregar_permiso(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name=GRUPO)
    content_type = ContentType.objects.get(app_label="clientes", model="cliente")
    permiso = Permission.objects.filter(content_type=content_type, codename=CODENAME).first()
    if permiso:
        grupo.permissions.add(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_permisos_facturacion_ventas_caja"),
    ]

    operations = [
        migrations.RunPython(quitar_permiso, agregar_permiso),
    ]
