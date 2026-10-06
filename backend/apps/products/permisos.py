PERMISOS_EDITAR_PRODUCTOS = ("products.add_producto", "products.change_producto")


def puede_editar_productos(user):
    """Quien puede crear o editar productos. También puede dar de alta,
    desde el formulario de producto, los catálogos que este usa (marca,
    línea, clase, unidad de medida y claves SAT): es parte de capturar el
    producto, no una administración aparte de esos catálogos."""
    return user.is_authenticated and any(user.has_perm(permiso) for permiso in PERMISOS_EDITAR_PRODUCTOS)
