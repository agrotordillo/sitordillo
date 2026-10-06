from django.db import migrations

# Antes de poner en la BD la regla de "una sola sucursal principal por
# usuario" (siguiente migración, B21 en docs/AUDITORIA.md): si algún usuario
# quedó con varias -el alta permitía marcar dos-, se conserva como principal
# la más antigua y las demás quedan como sucursales adicionales. No se borra
# ninguna asignación.


def dejar_una_principal(apps, schema_editor):
    AsignacionSucursal = apps.get_model("accounts", "AsignacionSucursal")
    vistos = set()
    sobrantes = []
    for asignacion_id, usuario_id in (
        AsignacionSucursal.objects.filter(es_principal=True).order_by("usuario_id", "pk").values_list("pk", "usuario_id")
    ):
        if usuario_id in vistos:
            sobrantes.append(asignacion_id)
        vistos.add(usuario_id)
    if sobrantes:
        AsignacionSucursal.objects.filter(pk__in=sobrantes).update(es_principal=False)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_permisos_movimiento_almacen"),
    ]

    operations = [
        migrations.RunPython(dejar_una_principal, migrations.RunPython.noop),
    ]
