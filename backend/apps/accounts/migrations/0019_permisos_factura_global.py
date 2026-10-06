from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# El cajero (grupo "Ventas y Caja") queda OBLIGADO a cerrar fiscalmente su
# propio turno: al cerrarlo, si quedaron ventas a Público en general sin
# facturar, la siguiente pantalla es generar/timbrar la factura global
# (ver products.views.turno_views.cerrar_turno_view). A diferencia de la
# Factura individual -ahí "Ventas y Caja" solo genera el borrador, y
# "Facturación" completa el timbrado-, aquí sí necesita view+add+change
# para poder terminarla sola, ahí mismo. "Facturación" recibe view+change
# para poder auditarla y reintentar un timbrado fallido, pero no "add":
# generarla es responsabilidad de quien cerró el turno, no de este grupo.
PERMISOS = {
    "Ventas y Caja": ["view", "add", "change"],
    "Facturación": ["view", "change"],
}


def _permisos(apps, acciones):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get(app_label="facturacion", model="facturaglobal")
    return [Permission.objects.get(content_type=content_type, codename=f"{a}_facturaglobal") for a in acciones]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    create_permissions(global_apps.get_app_config("facturacion"), verbosity=0)
    for nombre_grupo, acciones in PERMISOS.items():
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.add(*_permisos(apps, acciones))


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre_grupo, acciones in PERMISOS.items():
        grupo = Group.objects.filter(name=nombre_grupo).first()
        if grupo is not None:
            grupo.permissions.remove(*_permisos(apps, acciones))


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_permisos_turno_mostrador"),
        ("facturacion", "0003_facturaglobal"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
