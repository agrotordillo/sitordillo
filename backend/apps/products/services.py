from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .models import Turno


def abrir_turno(punto_venta, usuario, observaciones=""):
    """Abre un nuevo turno para esa caja (punto de venta de tipo Cobro).
    La restricción de "un solo turno abierto por punto de venta" vive en
    la base de datos (UniqueConstraint condicionado), así que aquí solo se
    traduce el IntegrityError de esa restricción a un mensaje claro -es la
    fuente de verdad ante dos aperturas simultáneas, no una revisión previa
    en Python que dejaría una ventana de carrera-. El try/except queda
    FUERA de cualquier transaction.atomic(): capturarlo dentro dejaría la
    conexión en estado de rollback pendiente para lo que siga en esa misma
    transacción."""
    turno = Turno(punto_venta=punto_venta, usuario=usuario, observaciones=observaciones)
    turno.full_clean()
    try:
        turno.save()
    except IntegrityError:
        raise ValidationError("Este punto de venta ya tiene un turno abierto.")
    return turno
