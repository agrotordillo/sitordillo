from django.db import migrations
from django.utils.text import slugify

# Catálogos oficiales SAT c_FormaPago y c_MetodoPago (CFDI 4.0).
# IMPORTANTE: capturados de memoria por el asistente — cotejar contra los
# catálogos oficiales vigentes del SAT antes de usarse en producción.
FORMAS_PAGO = [
    ("01", "Efectivo"),
    ("02", "Cheque nominativo"),
    ("03", "Transferencia electrónica de fondos"),
    ("04", "Tarjeta de crédito"),
    ("05", "Monedero electrónico"),
    ("06", "Dinero electrónico"),
    ("08", "Vales de despensa"),
    ("12", "Dación en pago"),
    ("13", "Pago por subrogación"),
    ("14", "Pago por consignación"),
    ("15", "Condonación"),
    ("17", "Compensación"),
    ("23", "Novación"),
    ("24", "Confusión"),
    ("25", "Remisión de deuda"),
    ("26", "Prescripción o caducidad"),
    ("27", "A satisfacción del acreedor"),
    ("28", "Tarjeta de débito"),
    ("29", "Tarjeta de servicios"),
    ("30", "Aplicación de anticipos"),
    ("31", "Intermediario pagos"),
    ("99", "Por definir"),
]

METODOS_PAGO = [
    ("PUE", "Pago en una sola exhibición"),
    ("PPD", "Pago en parcialidades o diferido"),
]


def seed_forma_pago(apps, schema_editor):
    FormaPago = apps.get_model("fiscal", "FormaPago")
    for clave, descripcion in FORMAS_PAGO:
        FormaPago.objects.update_or_create(
            clave=clave,
            defaults={
                "descripcion": descripcion,
                "folio": f"FPG-{clave}",
                "slug": slugify(f"{clave}-{descripcion}"),
            },
        )


def seed_metodo_pago(apps, schema_editor):
    MetodoPago = apps.get_model("fiscal", "MetodoPago")
    for clave, descripcion in METODOS_PAGO:
        MetodoPago.objects.update_or_create(
            clave=clave,
            defaults={
                "descripcion": descripcion,
                "folio": f"MPG-{clave}",
                "slug": slugify(f"{clave}-{descripcion}"),
            },
        )


def seed_catalogos(apps, schema_editor):
    seed_forma_pago(apps, schema_editor)
    seed_metodo_pago(apps, schema_editor)


def unseed_catalogos(apps, schema_editor):
    FormaPago = apps.get_model("fiscal", "FormaPago")
    MetodoPago = apps.get_model("fiscal", "MetodoPago")
    FormaPago.objects.filter(clave__in=[c for c, _ in FORMAS_PAGO]).delete()
    MetodoPago.objects.filter(clave__in=[c for c, _ in METODOS_PAGO]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("fiscal", "0005_forma_pago_metodo_pago_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalogos, unseed_catalogos),
    ]
