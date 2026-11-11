"""Los usuarios de caja y almacén de scv_web (importados como vendedores
inactivos, ver apps.core.scv_web.VendedoresLegado) no cuentan en las
comisiones sobre toda la venta de una sucursal: así los quita RH del Excel
de comisiones (P43 y P44, confirmado por el usuario el 2026-11-10). ANGELC,
la cuenta de caja que usa Miguel R., la crea la importación ya marcada."""
from django.db import migrations

CAJEROS_Y_ALMACENISTAS = ["angelc", "auri", "erika", "rbautista", "alex", "raque", "luisf"]


def marcar(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(username__in=CAJEROS_Y_ALMACENISTAS).update(comisiona_en_sucursal=False)


def desmarcar(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(username__in=CAJEROS_Y_ALMACENISTAS).update(comisiona_en_sucursal=True)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_user_comisiona_en_sucursal"),
    ]

    operations = [
        migrations.RunPython(marcar, desmarcar),
    ]
