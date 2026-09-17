# django imports
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from apps.core.views import permiso_denegado_view

# Respaldo: en circunstancias normales, PermisoDenegadoMiddleware
# (apps.core.middleware) ya intercepta cualquier PermissionDenied antes de
# que llegue aquí. handler403 solo entraría si por algún motivo la
# excepción se lanzara fuera del alcance de ese middleware.
handler403 = permiso_denegado_view

urlpatterns = [
    # Autenticación y administración
    path("", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),

    # API
    path("api/", include("apps.api.urls", namespace="api")),

    # Aplicaciones principales del sistema
    path("productos/", include("apps.products.urls", namespace="products")),
    path("proveedores/", include("apps.proveedores.urls", namespace="proveedores")),
    path("clientes/", include("apps.clientes.urls", namespace="clientes")),
    path("compras/", include("apps.compras.urls", namespace="compras")),
    path("inventario/", include("apps.inventario.urls", namespace="inventario")),
    path("traspasos/", include("apps.traspasos.urls", namespace="traspasos")),
    path("cotizaciones/", include("apps.cotizaciones.urls", namespace="cotizaciones")),
    path("ventas/", include("apps.ventas.urls", namespace="ventas")),
    path("cuentas-por-cobrar/", include("apps.cobros.urls", namespace="cobros")),
    path("comisiones/", include("apps.comisiones.urls", namespace="comisiones")),
    path("comisiones-ruta/", include("apps.comisiones_ruta.urls", namespace="comisiones_ruta")),
    path("pagos/", include("apps.pagos.urls", namespace="pagos")),
    path("facturacion/", include("apps.facturacion.urls", namespace="facturacion")),
    path("gastos/", include("apps.gastos.urls", namespace="gastos")),
    path('', TemplateView.as_view(template_name='core/home.html', extra_context={'active_module': 'home'}), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)