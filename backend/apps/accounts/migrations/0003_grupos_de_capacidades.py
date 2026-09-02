from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Capacidades componibles: un usuario puede pertenecer a varios grupos a
# la vez (p. ej. quien en una sucursal chica hace de almacenista, mostrador
# y caja). El Administrador no tiene grupo propio: se maneja con
# is_superuser, que ya ignora cualquier permiso granular en Django.
#
# Cada entrada es (app_label, nombre_del_modelo_en_minusculas, acciones).
# "compras.ordencompra" NO lleva "change" en Compras - Captura a propósito:
# OrdenCompraUpdateView es una sola vista que también avanza el estatus
# (Enviada/Recibida), y ese avance debe quedar fuera del alcance de
# "Compras residente". Sin una vista separada para enviar/cerrar pedido,
# el permiso genérico de Django no puede distinguir "editar mi borrador"
# de "aprobar/enviar la orden" - queda pendiente para cuando se protejan
# las vistas (siguiente fase), posiblemente con un permiso personalizado.
GRUPOS_PERMISOS = {
    "Ventas y Caja": [
        ("ventas", "venta", ["view", "add", "change"]),
        ("ventas", "ventadetalle", ["view", "add", "change"]),
        ("ventas", "devolucioncliente", ["view", "add"]),
        ("ventas", "devolucionclientedetalle", ["view", "add"]),
        ("clientes", "cliente", ["view", "add"]),
        ("cotizaciones", "cotizacion", ["view"]),
        ("cotizaciones", "cotizaciondetalle", ["view"]),
    ],
    "Mostrador y Cotización": [
        ("cotizaciones", "cotizacion", ["view", "add", "change"]),
        ("cotizaciones", "cotizaciondetalle", ["view", "add", "change"]),
        ("clientes", "cliente", ["view", "add"]),
    ],
    "Almacén": [
        ("inventario", "lote", ["view", "add", "change"]),
        ("inventario", "movimientoinventario", ["view", "add", "change"]),
        ("traspasos", "traspaso", ["view", "add", "change"]),
        ("traspasos", "traspasodetalle", ["view", "add", "change"]),
        ("traspasos", "traspasolote", ["view"]),
        ("products", "producto", ["view"]),
    ],
    "Facturación": [
        # Sin "delete": cancelar un CFDI es exclusivo del Administrador.
        ("facturacion", "factura", ["view", "add"]),
        ("ventas", "venta", ["view"]),
    ],
    "Compras - Captura": [
        ("compras", "ordencompra", ["view", "add"]),
        ("compras", "ordencompradetalle", ["view", "add"]),
        ("proveedores", "proveedor", ["view"]),
        ("products", "producto", ["view"]),
    ],
    "Compras - Completo": [
        ("compras", "ordencompra", ["view", "add", "change"]),
        ("compras", "ordencompradetalle", ["view", "add", "change"]),
        ("compras", "promocionproveedor", ["view", "add", "change"]),
        ("proveedores", "proveedor", ["view", "add", "change"]),
        ("products", "producto", ["view", "add", "change"]),
        ("pagos", "cuentaporpagar", ["view"]),
    ],
    "Pagos": [
        ("pagos", "cuentaporpagar", ["view", "add", "change"]),
        ("pagos", "pago", ["view", "add", "change"]),
        ("pagos", "banco", ["view", "add", "change"]),
        ("proveedores", "proveedor", ["view"]),
    ],
    "Gastos": [
        ("gastos", "gasto", ["view", "add", "change"]),
        ("gastos", "gastodistribucion", ["view", "add", "change"]),
        ("gastos", "categoriagasto", ["view", "add", "change"]),
        # CentroCosto es catálogo estructural: lo da de alta el Administrador,
        # este grupo solo lo consulta para elegirlo al registrar un gasto.
        ("gastos", "centrocosto", ["view"]),
        ("proveedores", "proveedor", ["view"]),
    ],
}


def _forzar_creacion_de_permisos(app_labels):
    """En un `migrate` desde cero, los permisos add/change/delete/view de
    un modelo los crea la señal post_migrate, que todavía no ha corrido
    cuando se ejecuta esta migración de datos (corre al final, después de
    aplicar TODAS las migraciones). Sin esto, esta migración funcionaría
    en una base de datos ya existente (como la nuestra, donde ya corrieron
    esas señales antes) pero fallaría silenciosamente en una instalación
    nueva. Se fuerza aquí con la misma función que usa Django internamente."""
    for app_label in app_labels:
        create_permissions(global_apps.get_app_config(app_label), verbosity=0)


def crear_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    app_labels = {app_label for reglas in GRUPOS_PERMISOS.values() for app_label, _, _ in reglas}
    _forzar_creacion_de_permisos(app_labels)

    for nombre_grupo, reglas in GRUPOS_PERMISOS.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        permisos = []
        for app_label, modelo, acciones in reglas:
            content_type = ContentType.objects.get(app_label=app_label, model=modelo)
            for accion in acciones:
                permisos.append(
                    Permission.objects.get(content_type=content_type, codename=f"{accion}_{modelo}")
                )
        grupo.permissions.set(permisos)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GRUPOS_PERMISOS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_asignacionsucursal"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("products", "0017_puntoventa"),
        ("proveedores", "0003_retarget_user_fk_to_accounts"),
        ("clientes", "0004_cliente_lista_precio"),
        ("compras", "0010_alter_ordencompradetalle_precio_unitario"),
        ("inventario", "0004_retarget_user_fk_to_accounts"),
        ("traspasos", "0002_retarget_user_fk_to_accounts"),
        ("ventas", "0002_retarget_user_fk_to_accounts"),
        ("cotizaciones", "0002_retarget_user_fk_to_accounts"),
        ("pagos", "0004_alter_pago_banco"),
        ("facturacion", "0002_retarget_user_fk_to_accounts"),
        ("gastos", "0002_alter_centrocosto_options_centrocosto_codigo_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
