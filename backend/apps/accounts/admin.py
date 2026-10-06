from django.contrib import admin
from django.contrib.auth.models import Group

# Usuarios, grupos (capacidades) y permisos se administran solo desde la
# pantalla de Usuarios del sistema, que respeta la regla de los módulos
# estrictos (ver apps.core.permisos_estrictos): en /admin/ un superusuario
# podría darse acceso a Gastos a sí mismo. Por eso el modelo User no se
# registra aquí y Group se retira del registro que hace django.contrib.auth.
admin.site.unregister(Group)
