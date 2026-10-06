import random
import string
import uuid

from django.db import migrations
from django.utils.text import slugify

ACCIONES = ("add", "change", "delete", "view")

# Ajustes al catálogo acordados con el negocio tras la revisión de la
# fase 1:
# - "Gastos personales" e "Impuesto sobre la renta" no son gasto de
#   operación (no cuentan en el punto de equilibrio); además, los conceptos
#   de gasto personal solo se cargan a centros de tipo Personal.
# - "Retiros Personales" y "Retiros y movimientos de la propietaria" eran
#   el mismo concepto: se conserva el segundo.
# - Se agregan dos conceptos que aparecen mucho en los vales reales y no
#   tenían dónde registrarse. "Mano de obra eventual" queda sin cuenta
#   contable hasta que contabilidad la defina.
GRUPOS_NO_OPERATIVOS = ["Gastos personales", "Impuesto sobre la renta"]
GRUPO_EXCLUSIVO_PERSONAL = "Gastos personales"
RETIRO_DUPLICADO = "Retiros Personales"
RETIRO_QUE_SE_CONSERVA = "Retiros y movimientos de la propietaria"

# (grupo, nombre, cuenta contable, naturaleza, qué registrar, ejemplos, criterio)
CONCEPTOS_NUEVOS = [
    (
        "Combustibles y transporte",
        "Maniobras y descarga de mercancía",
        "4101-021-000",
        "variable",
        "Pago a cargadores o terceros por subir, bajar o acomodar mercancía al recibirla, entregarla o "
        "traspasarla.",
        "Descarga de un tráiler de alimento; maniobra de carga para un traslado entre almacenes.",
        "No incluir el flete (va en Fletes y Acarreos) ni el sueldo del personal de planta.",
    ),
    (
        "Nómina y prestaciones",
        "Mano de obra eventual (jornales)",
        "",
        "variable",
        "Pago por día o por obra a trabajadores eventuales que no están en la nómina.",
        "Limpieza o chapeo del rancho; jornales de un proyecto agrícola; ayudante por un día.",
        "No incluir al personal de nómina (va en Sueldos y Salarios). Anotar en la descripción quién trabajó y "
        "cuántos días.",
    ),
]


def _folio_unico(Model, prefijo):
    caracteres = string.ascii_uppercase + string.digits
    while True:
        candidato = f"{prefijo}-{''.join(random.choices(caracteres, k=8))}"
        if not Model.objects.filter(folio=candidato).exists():
            return candidato


def _slug_unico(Model, nombre):
    base = slugify(nombre) or str(uuid.uuid4())
    slug = base
    contador = 2
    while Model.objects.filter(slug=slug).exists():
        slug = f"{base}-{contador}"
        contador += 1
    return slug


def _renombrar_permisos(apps, modelo_viejo, modelo_nuevo, nombre_nuevo):
    """La migración 0009 renombra el content type del modelo, pero Django
    no renombra los permisos (siguen como `view_categoriagasto`): aquí se
    les pone el codename nuevo, conservando a qué grupos y usuarios estaban
    asignados. Si ya existen permisos con el nombre nuevo (en una
    instalación nueva los crea accounts.0003 con el modelo actual), se
    pasan las asignaciones a esos y se borran los viejos."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(app_label="gastos", model=modelo_nuevo)
    for accion in ACCIONES:
        viejo = Permission.objects.filter(
            content_type__app_label="gastos", codename=f"{accion}_{modelo_viejo}"
        ).first()
        if viejo is None:
            continue
        nuevo = Permission.objects.filter(content_type=content_type, codename=f"{accion}_{modelo_nuevo}").first()
        if nuevo is None:
            viejo.content_type = content_type
            viejo.codename = f"{accion}_{modelo_nuevo}"
            viejo.name = f"Can {accion} {nombre_nuevo}"
            viejo.save()
            continue
        for grupo in viejo.group_set.all():
            grupo.permissions.add(nuevo)
        for usuario in viejo.user_set.all():
            usuario.user_permissions.add(nuevo)
        viejo.delete()
    ContentType.objects.filter(app_label="gastos", model=modelo_viejo).delete()


def _permisos_de_captura(apps, modelo):
    Permission = apps.get_model("auth", "Permission")
    return Permission.objects.filter(
        content_type__app_label="gastos", codename__in=[f"add_{modelo}", f"change_{modelo}"]
    )


def aplicar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GrupoGasto = apps.get_model("gastos", "GrupoGasto")
    ConceptoGasto = apps.get_model("gastos", "ConceptoGasto")
    Gasto = apps.get_model("gastos", "Gasto")

    _renombrar_permisos(apps, "categoriagasto", "conceptogasto", "Concepto de gasto")

    # El catálogo de conceptos es de contabilidad: el grupo "Gastos" solo lo
    # consulta para elegir el concepto al capturar, igual que los centros
    # de costo y los vehículos.
    grupo_gastos = Group.objects.filter(name="Gastos").first()
    if grupo_gastos is not None:
        grupo_gastos.permissions.remove(*_permisos_de_captura(apps, "conceptogasto"))

    GrupoGasto.objects.filter(nombre__in=GRUPOS_NO_OPERATIVOS).update(clasificacion="no_operativo")
    GrupoGasto.objects.filter(nombre=GRUPO_EXCLUSIVO_PERSONAL).update(exclusivo_personal=True)

    duplicado = ConceptoGasto.objects.filter(nombre=RETIRO_DUPLICADO).first()
    conservado = ConceptoGasto.objects.filter(nombre=RETIRO_QUE_SE_CONSERVA).first()
    if duplicado is not None and conservado is not None:
        Gasto.objects.filter(concepto_gasto=duplicado).update(concepto_gasto=conservado)
        duplicado.delete()

    for grupo, nombre, cuenta, naturaleza, descripcion, ejemplos, criterio in CONCEPTOS_NUEVOS:
        grupo_obj = GrupoGasto.objects.filter(nombre=grupo).first()
        if grupo_obj is None or ConceptoGasto.objects.filter(nombre__iexact=nombre).exists():
            continue
        ConceptoGasto.objects.create(
            uuid=uuid.uuid4(),
            folio=_folio_unico(ConceptoGasto, "CAT"),
            slug=_slug_unico(ConceptoGasto, nombre),
            grupo=grupo_obj,
            nombre=nombre,
            cuenta_contable=cuenta,
            naturaleza=naturaleza,
            descripcion=descripcion,
            ejemplos=ejemplos,
            criterio=criterio,
        )


def revertir(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GrupoGasto = apps.get_model("gastos", "GrupoGasto")
    ConceptoGasto = apps.get_model("gastos", "ConceptoGasto")

    ConceptoGasto.objects.filter(nombre__in=[c[1] for c in CONCEPTOS_NUEVOS], gastos__isnull=True).delete()
    GrupoGasto.objects.filter(nombre__in=GRUPOS_NO_OPERATIVOS).update(clasificacion="gasto")
    GrupoGasto.objects.filter(nombre=GRUPO_EXCLUSIVO_PERSONAL).update(exclusivo_personal=False)
    # "Retiros Personales" no se recrea: sus gastos ya quedaron en el concepto
    # que se conservó.

    grupo_gastos = Group.objects.filter(name="Gastos").first()
    if grupo_gastos is not None:
        grupo_gastos.permissions.add(*_permisos_de_captura(apps, "conceptogasto"))
    _renombrar_permisos(apps, "conceptogasto", "categoriagasto", "Categoría de gasto")


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0009_renombrar_concepto_gasto"),
        ("accounts", "0003_grupos_de_capacidades"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
