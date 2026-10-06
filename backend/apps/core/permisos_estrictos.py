"""Permisos estrictos: módulos donde ser superusuario no basta.

Vive aparte de apps.core.permissions porque lo importa el modelo de
usuario (accounts.User), y ese módulo importa django.contrib.auth.mixins,
que a su vez necesita el modelo de usuario ya cargado."""
from django.db.models import Q

# Módulos con información confidencial cuyos permisos ni siquiera un
# Administrador (superusuario) tiene por el solo hecho de serlo: para
# entrar necesita la capacidad (grupo) asignada a su nombre, igual que
# cualquier otro usuario, y esa capacidad solo se la puede dar alguien que
# ya la tenga (ver accounts.forms y User.has_perm).
#
# Es una barrera dentro del sistema, no contra quien tiene acceso al
# servidor o a la base de datos: desde ahí siempre se puede otorgar (ver el
# comando `otorgar_acceso_gastos`).
APPS_PERMISO_ESTRICTO = frozenset({"gastos"})


def es_permiso_estricto(perm):
    return perm.split(".", 1)[0] in APPS_PERMISO_ESTRICTO


def permisos_explicitos(user):
    """Permisos de los módulos estrictos que el usuario tiene asignados de
    verdad (directo o por sus grupos), sin el atajo de superusuario. Se
    guardan en la instancia, como hace Django con su propia caché de
    permisos, para no consultar la base en cada `{% if perms... %}`."""
    if not user.is_active or user.is_anonymous:
        return frozenset()
    if not hasattr(user, "_permisos_explicitos_cache"):
        from django.contrib.auth.models import Permission

        filas = (
            Permission.objects.filter(Q(user=user) | Q(group__user=user))
            .filter(content_type__app_label__in=APPS_PERMISO_ESTRICTO)
            .values_list("content_type__app_label", "codename")
            .distinct()
        )
        user._permisos_explicitos_cache = frozenset(f"{app}.{codename}" for app, codename in filas)
    return user._permisos_explicitos_cache


def grupos_protegidos():
    """Grupos (capacidades) que dan algún permiso de un módulo estricto."""
    from django.contrib.auth.models import Group

    return Group.objects.filter(permissions__content_type__app_label__in=APPS_PERMISO_ESTRICTO).distinct()


def grupos_que_no_puede_otorgar(solicitante):
    """Capacidades protegidas que `solicitante` no puede dar ni quitar a
    nadie porque él mismo no las tiene."""
    return grupos_protegidos().exclude(user=solicitante)
