def almacenes_visibles(user):
    """Almacenes a los que este usuario queda restringido, o `None` si no
    tiene restricción (superusuario, o sin ninguna fila en
    AsignacionSucursal -pensado para Administrador y Auxiliar
    administrador, que ven todas las sucursales).

    Un usuario puede tener más de una asignación (quien cubre turnos de
    descanso en varias sucursales), así que el resultado es un conjunto,
    no un único almacén."""
    if user.is_superuser or not user.is_authenticated:
        return None

    from apps.products.models import Almacen

    almacen_ids = list(user.asignaciones_sucursal.values_list("almacen_id", flat=True))
    if not almacen_ids:
        return None
    return Almacen.objects.filter(pk__in=almacen_ids)


def almacen_principal(user):
    """La sucursal fija de un usuario de mostrador (su AsignacionSucursal
    con es_principal=True), para precargarla en cotización/venta sin que
    tenga que elegirla cada vez. Devuelve `None` si el usuario no tiene una
    sola sucursal principal clara -sin restricción (Administrador/Auxiliar
    administrador), sin ninguna asignación, o con varias y ninguna marcada
    principal-, caso en el que sigue teniendo que elegirla a mano."""
    if user.is_superuser or not user.is_authenticated:
        return None

    asignacion = user.asignaciones_sucursal.filter(es_principal=True).first()
    return asignacion.almacen if asignacion else None
