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
