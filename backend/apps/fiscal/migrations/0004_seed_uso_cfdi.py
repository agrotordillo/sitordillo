from django.db import migrations
from django.utils.text import slugify

# Catálogo oficial SAT c_UsoCFDI (CFDI 4.0).
# IMPORTANTE: capturado de memoria por el asistente — cotejar contra el
# catálogo oficial vigente del SAT antes de usarse en producción.
# No incluye la matriz de compatibilidad Uso CFDI <-> Régimen Fiscal
# (se define en la Fase 7 - Facturación, junto con la validación de CFDI).
USOS_CFDI = [
    ("G01", "Adquisición de mercancías", True, True),
    ("G02", "Devoluciones, descuentos o bonificaciones", True, True),
    ("G03", "Gastos en general", True, True),
    ("I01", "Construcciones", True, True),
    ("I02", "Mobiliario y equipo de oficina por inversiones", True, True),
    ("I03", "Equipo de transporte", True, True),
    ("I04", "Equipo de computo y accesorios", True, True),
    ("I05", "Dados, troqueles, moldes, matrices y otros activos", True, True),
    ("I06", "Comunicaciones telefónicas", True, True),
    ("I07", "Comunicaciones satelitales", True, True),
    ("I08", "Otra maquinaria y equipo", True, True),
    ("D01", "Honorarios médicos, dentales y gastos hospitalarios", True, False),
    ("D02", "Gastos médicos por incapacidad o discapacidad", True, False),
    ("D03", "Gastos funerales", True, False),
    ("D04", "Donativos", True, False),
    ("D05", "Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)", True, False),
    ("D06", "Aportaciones voluntarias al SAR", True, False),
    ("D07", "Primas por seguros de gastos médicos", True, False),
    ("D08", "Gastos de transportación escolar obligatoria", True, False),
    ("D09", "Depósitos en cuentas para el ahorro, pensiones", True, False),
    ("D10", "Pagos por servicios educativos (colegiaturas)", True, False),
    ("S01", "Sin efectos fiscales", True, True),
    ("CP01", "Pagos", True, True),
    ("CN01", "Nómina", True, False),
]


def seed_usos_cfdi(apps, schema_editor):
    UsoCFDI = apps.get_model("fiscal", "UsoCFDI")
    for clave, descripcion, aplica_fisica, aplica_moral in USOS_CFDI:
        UsoCFDI.objects.update_or_create(
            clave=clave,
            defaults={
                "descripcion": descripcion,
                "aplica_fisica": aplica_fisica,
                "aplica_moral": aplica_moral,
                "folio": f"UCF-{clave}",
                "slug": slugify(f"{clave}-{descripcion}"),
            },
        )


def unseed_usos_cfdi(apps, schema_editor):
    UsoCFDI = apps.get_model("fiscal", "UsoCFDI")
    claves = [clave for clave, *_ in USOS_CFDI]
    UsoCFDI.objects.filter(clave__in=claves).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("fiscal", "0003_uso_cfdi_initial"),
    ]

    operations = [
        migrations.RunPython(seed_usos_cfdi, unseed_usos_cfdi),
    ]
