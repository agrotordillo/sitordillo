"""Categoría MASCOTAS GANADOR PREMIUM: la línea Ganador Premium de ADM
estaba revuelta en MASCOTAS ADM con Fulllife, Best Choice, Minino y Poder
Canino, y es la única de ADM que cuenta como alimento premium en las
comisiones de los médicos (decisión del usuario, 2026-11-11). Se pasan a ella
los productos de ALIMENTOS / MASCOTAS ADM cuyo nombre empieza con
"GANADOR PREM". Los que se den de alta después se clasifican a mano."""
import uuid

from django.db import migrations

NOMBRE = "MASCOTAS GANADOR PREMIUM"


def crear(apps, schema_editor):
    Categoria = apps.get_model("products", "Categoria")
    Producto = apps.get_model("products", "Producto")
    # El modelo histórico no tiene el save() de BaseAbstractModel: folio y
    # slug van a mano.
    categoria = Categoria.objects.filter(nombre=NOMBRE).first() or Categoria.objects.create(
        nombre=NOMBRE, uuid=uuid.uuid4(), folio="CAT-GANPREM1", slug="mascotas-ganador-premium",
    )
    Producto.objects.filter(
        linea__nombre="ALIMENTOS", categoria__nombre="MASCOTAS ADM", nombre__istartswith="GANADOR PREM",
    ).update(categoria=categoria)


def deshacer(apps, schema_editor):
    Categoria = apps.get_model("products", "Categoria")
    Producto = apps.get_model("products", "Producto")
    adm = Categoria.objects.filter(nombre="MASCOTAS ADM").first()
    if adm:
        Producto.objects.filter(categoria__nombre=NOMBRE).update(categoria=adm)
    Categoria.objects.filter(nombre=NOMBRE, productos__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0032_subcategoria_independiente"),
    ]

    operations = [
        migrations.RunPython(crear, deshacer),
    ]
