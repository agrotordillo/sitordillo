# django imports
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # API
    path("api/", include("apps.api.urls", namespace="api")),

    # Aplicaciones principales del sistema
    path("productos/", include("apps.products.urls", namespace="products")),
    path('', TemplateView.as_view(template_name='core/home.html', extra_context={'active_module': 'home'}), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)