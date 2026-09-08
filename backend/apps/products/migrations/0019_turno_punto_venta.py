# Ata Turno a PuntoVenta (una caja) en vez de a Almacen (la sucursal
# completa): así una sucursal puede operar con más de una caja abierta a
# la vez, cada una con su propio cajero -hoy en la práctica se sigue
# usando una sola por sucursal, pero el modelo ya no lo impide-. Se hace
# ahora, antes de que exista historial real de turnos en producción,
# porque después de acumular datos este cambio sería mucho más caro.
#
# Cada sucursal sin ningún PuntoVenta capturado (el caso de todas hoy)
# recibe uno por default ("CAJA1" / "Caja 1", tipo Cobro) para no dejar
# a nadie sin dónde abrir su turno. Si ya existieran turnos (hoy no hay
# ninguno en ningún ambiente conocido de este proyecto), se reasignan a
# ese punto de venta default de su sucursal.
#
# La función de reversa de la migración de datos es un no-op: si algún
# día hay que revertir este cambio con datos reales ya cargados, hace
# falta una intervención manual (decidir a qué almacén vuelve cada
# turno cuando puede haber varias cajas por sucursal) - no es un caso
# que se espere necesitar.
#
# Esta migración solo agrega la columna (nullable) y hace el llenado de
# datos; el resto del cambio de esquema (hacerla obligatoria, quitar
# "almacen", mover el índice/restricción única) queda en
# 0020_turno_punto_venta_finalizar porque Postgres no permite hacer
# ALTER TABLE sobre una tabla que tiene eventos de trigger pendientes de
# un INSERT/UPDATE hecho en la misma transacción -mezclar el llenado de
# datos con el DDL final en una sola migración truena con
# "no se puede hacer ALTER TABLE... tiene eventos de trigger pendientes".
import uuid as uuid_lib

import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def poblar_puntos_venta_y_reasignar_turnos(apps, schema_editor):
    Almacen = apps.get_model("products", "Almacen")
    PuntoVenta = apps.get_model("products", "PuntoVenta")
    Turno = apps.get_model("products", "Turno")

    def punto_venta_default(almacen):
        punto_venta = PuntoVenta.objects.filter(almacen=almacen, tipo="cobro").order_by("id").first()
        if punto_venta:
            return punto_venta
        # Un modelo "histórico" (apps.get_model) no trae el save() de
        # BaseAbstractModel que genera folio/slug/uuid -hay que ponerlos a
        # mano aquí, igual de únicos, para no violar esas restricciones.
        nuevo_uuid = uuid_lib.uuid4()
        return PuntoVenta.objects.create(
            uuid=nuevo_uuid,
            folio=f"PDV-{nuevo_uuid.hex[:8].upper()}",
            slug=slugify(f"{almacen.pk}-caja1-{nuevo_uuid.hex[:8]}"),
            almacen=almacen, codigo="CAJA1", nombre="Caja 1", tipo="cobro",
        )

    for almacen in Almacen.objects.filter(tipo="sucursal"):
        if Turno.objects.filter(almacen=almacen).exists():
            punto_venta = punto_venta_default(almacen)
            Turno.objects.filter(almacen=almacen).update(punto_venta=punto_venta)

    # Sucursales sin ningún turno histórico también reciben su caja
    # default, para que ya exista al abrir el primer turno.
    for almacen in Almacen.objects.filter(tipo="sucursal"):
        if not PuntoVenta.objects.filter(almacen=almacen, tipo="cobro").exists():
            punto_venta_default(almacen)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0018_turno"),
    ]

    operations = [
        migrations.AddField(
            model_name="turno",
            name="punto_venta",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="turnos",
                to="products.puntoventa",
                verbose_name="Punto de venta",
            ),
        ),
        migrations.RunPython(poblar_puntos_venta_y_reasignar_turnos, migrations.RunPython.noop),
    ]
