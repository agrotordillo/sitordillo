from django.db import migrations
from django.utils.text import slugify

# Catálogo oficial SAT c_RegimenFiscal (CFDI 4.0).
# IMPORTANTE: capturado de memoria por el asistente — cotejar contra el
# catálogo oficial vigente del SAT antes de usarse en producción.
REGIMENES = [
    ("601", "General de Ley Personas Morales", False, True),
    ("603", "Personas Morales con Fines no Lucrativos", False, True),
    ("605", "Sueldos y Salarios e Ingresos Asimilados a Salarios", True, False),
    ("606", "Arrendamiento", True, False),
    ("607", "Régimen de Enajenación o Adquisición de Bienes", True, False),
    ("608", "Demás ingresos", True, False),
    ("609", "Consolidación", False, True),
    ("610", "Residentes en el Extranjero sin Establecimiento Permanente en México", True, True),
    ("611", "Ingresos por Dividendos (socios y accionistas)", True, False),
    ("612", "Personas Físicas con Actividades Empresariales y Profesionales", True, False),
    ("614", "Ingresos por intereses", True, False),
    ("615", "Régimen de los ingresos por obtención de premios", True, False),
    ("616", "Sin obligaciones fiscales", True, False),
    ("620", "Sociedades Cooperativas de Producción que optan por diferir sus ingresos", False, True),
    ("621", "Incorporación Fiscal", True, False),
    ("622", "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras", True, True),
    ("623", "Opcional para Grupos de Sociedades", False, True),
    ("624", "Coordinados", False, True),
    ("625", "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas", True, False),
    ("626", "Régimen Simplificado de Confianza (RESICO)", True, True),
]


def seed_regimenes(apps, schema_editor):
    # apps.get_model() devuelve el modelo "histórico": trae los campos tal
    # como estaban en esta migración, pero NO el save() de BaseAbstractModel
    # que autogenera folio/slug. Por eso se calculan aquí a mano.
    RegimenFiscal = apps.get_model("fiscal", "RegimenFiscal")
    for clave, descripcion, aplica_fisica, aplica_moral in REGIMENES:
        RegimenFiscal.objects.update_or_create(
            clave=clave,
            defaults={
                "descripcion": descripcion,
                "aplica_fisica": aplica_fisica,
                "aplica_moral": aplica_moral,
                "folio": f"RFI-{clave}",
                "slug": slugify(f"{clave}-{descripcion}"),
            },
        )


def unseed_regimenes(apps, schema_editor):
    RegimenFiscal = apps.get_model("fiscal", "RegimenFiscal")
    claves = [clave for clave, *_ in REGIMENES]
    RegimenFiscal.objects.filter(clave__in=claves).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("fiscal", "0001_regimen_fiscal_initial"),
    ]

    operations = [
        migrations.RunPython(seed_regimenes, unseed_regimenes),
    ]
