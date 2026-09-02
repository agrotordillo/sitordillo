from django.contrib.auth.mixins import UserPassesTestMixin


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Para las pocas pantallas que son un invariante de negocio exclusivo
    del Administrador (hoy: gestionar a qué sucursal queda restringido cada
    usuario) y que por eso no deben depender de un permiso de Django
    reasignable -a diferencia de un catálogo estructural cualquiera (Marca,
    Almacén, etc.), donde si mañana se decide delegarlo a un grupo, basta
    con otorgar el permiso correspondiente sin tocar código. Un
    superusuario ya ignora cualquier permiso granular en Django, así que
    esto solo bloquea a quien no lo es."""

    def test_func(self):
        return self.request.user.is_superuser
