from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Desde aquí Gastos es un módulo de permisos estrictos (ver
# apps.core.permisos_estrictos): ni el Administrador entra sin la capacidad
# asignada. Por eso el mantenimiento de los catálogos, que antes hacía el
# Administrador por serlo, pasa a su propia capacidad, y alguien tiene que
# empezar con el acceso para poder dárselo a los demás: el usuario "admin"
# si existe; si no, se otorga desde el servidor con el comando
# `otorgar_acceso_gastos`.
GRUPO_CAPTURA = "Gastos"
GRUPO_ADMINISTRACION = "Gastos - Administración"
PERMISOS_ADMINISTRACION = [
    ("conceptogasto", ["view", "add", "change"]),
    ("centrocosto", ["view", "add", "change"]),
    ("vehiculo", ["view", "add", "change"]),
    ("grupogasto", ["view"]),
    ("bitacoraaccesogastos", ["view"]),
]
USUARIO_INICIAL = "admin"
NOTA_INICIAL = "Acceso inicial al proteger el módulo de Gastos."


def aplicar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("accounts", "User")
    Bitacora = apps.get_model("gastos", "BitacoraAccesoGastos")

    # En un migrate desde cero los permisos de los modelos nuevos todavía no
    # existen (los crea la señal post_migrate al final); ver accounts.0003.
    create_permissions(global_apps.get_app_config("gastos"), verbosity=0)

    administracion, _ = Group.objects.get_or_create(name=GRUPO_ADMINISTRACION)
    administracion.permissions.add(*[
        Permission.objects.get(content_type__app_label="gastos", codename=f"{accion}_{modelo}")
        for modelo, acciones in PERMISOS_ADMINISTRACION
        for accion in acciones
    ])

    usuario = User.objects.filter(username=USUARIO_INICIAL).first()
    if usuario is None:
        return
    for grupo in Group.objects.filter(name__in=[GRUPO_CAPTURA, GRUPO_ADMINISTRACION]):
        if not usuario.groups.filter(pk=grupo.pk).exists():
            usuario.groups.add(grupo)
            Bitacora.objects.create(
                usuario=usuario, grupo=grupo, grupo_nombre=grupo.name, accion="otorgada", nota=NOTA_INICIAL,
            )


def revertir(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Bitacora = apps.get_model("gastos", "BitacoraAccesoGastos")
    Bitacora.objects.filter(nota=NOTA_INICIAL).delete()
    Group.objects.filter(name=GRUPO_ADMINISTRACION).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0011_bitacora_acceso_gastos"),
        ("accounts", "0003_grupos_de_capacidades"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
