from django.db import migrations

# Corrige un hueco de la Fase 2 (ver accounts/migrations/0003): el grupo
# "Facturación" tenia view+add sobre Factura pero no change, así que nadie
# de ese grupo podía completar el timbrado (solo el Administrador). Se
# revisó contra el sistema legado (scvweb): ahí "Cancelación de CFDI" y
# "Cancelación de documento por supervisor" son pantallas aparte y más
# privilegiadas que el flujo normal de facturar (sin calificador de
# "supervisor" en su nombre) - confirma que timbrar es una acción rutinaria
# del rol de facturación, no una que deba quedar reservada al
# Administrador como sí lo es cancelar (delete_factura, que se deja
# intacto).


def agregar_change_factura(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name="Facturación")
    content_type = ContentType.objects.get(app_label="facturacion", model="factura")
    permiso = Permission.objects.get(content_type=content_type, codename="change_factura")
    grupo.permissions.add(permiso)


def quitar_change_factura(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    grupo = Group.objects.get(name="Facturación")
    content_type = ContentType.objects.get(app_label="facturacion", model="factura")
    permiso = Permission.objects.get(content_type=content_type, codename="change_factura")
    grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_grupos_de_capacidades"),
    ]

    operations = [
        migrations.RunPython(agregar_change_factura, quitar_change_factura),
    ]
