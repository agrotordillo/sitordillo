import random
import string
import uuid

from django.db import migrations
from django.utils.text import slugify

# Catálogo inicial de CategoriaGasto, tomado de datos/CATALAGO GASTO.xlsx
# (plan de cuentas contable completo del negocio). Se importa el rubro
# "GASTOS" completo (cuentas mayores 4101, 4103-4107 y 4114; se excluye
# 4102 "GASTOS GENERALES A CRÉDITO" porque repite los mismos nombres de
# 4101 -es solo la distinción contable crédito/contado, que este sistema
# no modela como categoría-), a nivel de subcuenta (segundo nivel del
# código, ej. 4101-009-000): cuando una subcuenta del catálogo original se
# desglosa en cuentas de detalle más finas (ej. Sueldos y Salarios ->
# Sueldos, Comisiones, Séptimo día...), esas se agrupan en la categoría de
# la subcuenta en vez de crear una categoría por cada detalle.
#
# `naturaleza` (fijo/variable) es una propuesta inicial de sentido común
# para el reporte de punto de equilibrio (ver ReportePuntoEquilibrioView);
# no viene del Excel -ese catálogo es puramente contable y no distingue
# fijo/variable- así que es editable libremente desde Gastos > Categorías
# si el criterio real de negocio difiere.
CATEGORIAS = [
    # --- 4101 GASTOS GENERALES ---
    ("Sueldos y Salarios", "fijo", "Cuenta contable 4101-001-000. Incluye sueldos, comisiones, séptimo día, "
     "premios de asistencia y puntualidad, despensa, vacaciones, prima vacacional y dominical, días festivos, "
     "gratificaciones, primas de antigüedad, aguinaldo, indemnización y otras prestaciones."),
    ("Impuestos Patronales", "fijo", "Cuenta contable 4101-002-000. Cuota IMSS, aportaciones al Infonavit y al "
     "SAR, impuesto estatal sobre nóminas."),
    ("Combustibles y Lubricantes", "variable", "Cuenta contable 4101-003-000."),
    ("Cuota IEPS", "variable", "Cuenta contable 4101-004-000."),
    ("Honorarios", "variable", "Cuenta contable 4101-005-000. Honorarios a personas físicas y morales."),
    ("Refacciones", "variable", "Cuenta contable 4101-006-000."),
    ("Reparaciones y Servicios", "variable", "Cuenta contable 4101-007-000."),
    ("Viáticos y Gastos de Viaje", "variable", "Cuenta contable 4101-008-000."),
    ("Teléfono e Internet", "fijo", "Cuenta contable 4101-009-000."),
    ("Agua", "fijo", "Cuenta contable 4101-010-000."),
    ("Energía Eléctrica", "fijo", "Cuenta contable 4101-011-000."),
    ("Artículos de Trabajo", "variable", "Cuenta contable 4101-012-000."),
    ("Artículos de Limpieza", "variable", "Cuenta contable 4101-013-000."),
    ("Papelería y Artículos de Oficina", "variable", "Cuenta contable 4101-014-000."),
    ("Mantenimiento y Conservación", "variable", "Cuenta contable 4101-015-000."),
    ("Seguros y Fianzas", "fijo", "Cuenta contable 4101-016-000."),
    ("Otros Impuestos y Derechos", "fijo", "Cuenta contable 4101-017-000. Impuesto sobre hospedaje, derechos, "
     "refrendos."),
    ("Recargos Fiscales", "variable", "Cuenta contable 4101-018-000."),
    ("Cuotas y Suscripciones", "fijo", "Cuenta contable 4101-019-000."),
    ("Propaganda y Publicidad", "variable", "Cuenta contable 4101-020-000."),
    ("Fletes y Acarreos", "variable", "Cuenta contable 4101-021-000."),
    ("Mantenimiento y Actualización de Software", "fijo", "Cuenta contable 4101-022-000."),
    ("Uniformes", "variable", "Cuenta contable 4101-023-000."),
    ("Atención a Clientes", "variable", "Cuenta contable 4101-024-000."),
    ("Gas", "fijo", "Cuenta contable 4101-025-000."),
    ("Arrendamientos", "fijo", "Cuenta contable 4101-026-000. A personas físicas, morales y leasing."),
    ("Servicios de Cable", "fijo", "Cuenta contable 4101-027-000."),
    ("Empaques y Envolturas", "variable", "Cuenta contable 4101-028-000."),
    ("Capacitación a Empleados", "variable", "Cuenta contable 4101-029-000."),
    ("Herramientas de Trabajo", "variable", "Cuenta contable 4101-030-000."),
    ("Gastos al 8%", "variable", "Cuenta contable 4101-031-000."),
    ("Gastos No Deducibles", "variable", "Cuenta contable 4101-039-000. Sin requisitos fiscales, multas, "
     "actualización, gastos de ejecución."),
    ("Otros Gastos", "variable", "Cuenta contable 4101-040-000. Gravados al 16%, al 0% y exentos."),
    ("Mantenimiento a Vehículo", "variable", "Cuenta contable 4101-041-000."),
    ("Gastos de Viaje y Representación", "variable", "Cuenta contable 4101-042-000."),
    ("Accesorios para Equipo de Cómputo", "variable", "Cuenta contable 4101-043-000."),
    ("Recolección de Residuos Biológicos", "variable", "Cuenta contable 4101-044-000."),
    # --- 4103 GASTOS FINANCIEROS ---
    ("Comisiones Bancarias", "variable", "Cuenta contable 4103-001-000."),
    ("Intereses a Cargo Bancario", "variable", "Cuenta contable 4103-002-000."),
    ("Otros Gastos Financieros", "variable", "Cuenta contable 4103-003-000."),
    ("Ajuste en Centavos", "variable", "Cuenta contable 4103-004-000."),
    ("Intereses por Financiamiento", "variable", "Cuenta contable 4103-005-000."),
    ("Intereses Ordinarios", "variable", "Cuenta contable 4103-006-000."),
    ("Servicio de Factoraje Exento", "variable", "Cuenta contable 4103-007-000."),
    ("Intereses por Financiamiento Exento", "variable", "Cuenta contable 4103-008-000."),
    ("Gastos Financieros sin IVA", "variable", "Cuenta contable 4103-009-000."),
    ("Intereses Exentos", "variable", "Cuenta contable 4103-010-000."),
    ("Comisiones TPV", "variable", "Cuenta contable 4103-080-000."),
    # --- 4104 DEPRECIACION CONTABLE ---
    ("Depreciación de Edificio", "fijo", "Cuenta contable 4104-001-000."),
    ("Depreciación de Maquinaria y Equipo", "fijo", "Cuenta contable 4104-002-000."),
    ("Depreciación de Equipo de Reparto", "fijo", "Cuenta contable 4104-003-000."),
    ("Depreciación de Mobiliario y Equipo de Oficina", "fijo", "Cuenta contable 4104-004-000."),
    ("Depreciación de Equipo de Cómputo", "fijo", "Cuenta contable 4104-005-000."),
    ("Depreciación de Comunicación", "fijo", "Cuenta contable 4104-006-000."),
    ("Depreciación de Otros Activos Fijos", "fijo", "Cuenta contable 4104-007-000."),
    # --- 4105 AMORTIZACION CONTABLE ---
    ("Amortización de Gastos de Instalación", "fijo", "Cuenta contable 4105-001-000."),
    # --- 4106 GASTOS PERSONALES ---
    ("Gastos Médicos", "variable", "Cuenta contable 4106-001-000."),
    ("Tarjeta Personal", "variable", "Cuenta contable 4106-002-000."),
    ("Colegiatura", "fijo", "Cuenta contable 4106-003-000."),
    ("Rerito Arrendamiento", "fijo", "Cuenta contable 4106-004-000. Nombre tal como está en el catálogo contable "
     "original (posible error de captura ahí)."),
    # --- 4107 IMPUESTO SOBRE LA RENTA ---
    ("Impuesto Sobre la Renta", "fijo", "Cuenta contable 4107-001-000."),
    # --- 4114 GASTOS SOBRE COMPRAS ---
    ("Gastos Sobre Compras", "variable", "Cuenta contable 4114-001-000."),
]


def _folio_unico(Model, prefijo="CAT"):
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


def cargar_categorias(apps, schema_editor):
    # apps.get_model() da el modelo histórico -sin los métodos de
    # BaseAbstractModel (get_folio_prefix/save con folio y slug
    # automáticos)-, así que folio/slug/uuid se generan aquí a mano con el
    # mismo algoritmo del modelo real (ver apps.core.models.BaseAbstractModel).
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    for nombre, naturaleza, descripcion in CATEGORIAS:
        if CategoriaGasto.objects.filter(nombre=nombre).exists():
            continue
        CategoriaGasto.objects.create(
            uuid=uuid.uuid4(),
            folio=_folio_unico(CategoriaGasto),
            slug=_slug_unico(CategoriaGasto, nombre),
            nombre=nombre,
            naturaleza=naturaleza,
            descripcion=descripcion,
        )


def quitar_categorias(apps, schema_editor):
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    nombres = [nombre for nombre, _, _ in CATEGORIAS]
    CategoriaGasto.objects.filter(nombre__in=nombres).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0002_alter_centrocosto_options_centrocosto_codigo_and_more"),
    ]

    operations = [
        migrations.RunPython(cargar_categorias, quitar_categorias),
    ]
