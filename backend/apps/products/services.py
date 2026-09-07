from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import Turno


def abrir_turno(almacen, usuario, observaciones=""):
    """Abre un nuevo turno para la sucursal. La restricción de "un solo
    turno abierto por almacén" vive en la base de datos (UniqueConstraint
    condicionado), así que aquí solo se traduce el IntegrityError de esa
    restricción a un mensaje claro -es la fuente de verdad ante dos
    aperturas simultáneas, no una revisión previa en Python que dejaría una
    ventana de carrera-. El try/except queda FUERA de cualquier
    transaction.atomic(): capturarlo dentro dejaría la conexión en estado
    de rollback pendiente para lo que siga en esa misma transacción."""
    turno = Turno(almacen=almacen, usuario=usuario, observaciones=observaciones)
    turno.full_clean()
    try:
        turno.save()
    except IntegrityError:
        raise ValidationError("Esta sucursal ya tiene un turno abierto.")
    return turno
