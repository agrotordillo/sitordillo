from django.urls import path

from .views.cotizacion_views import CotizacionCreateView, CotizacionListView
from .views.conversion_views import buscar_cotizacion_view, convertir_cotizacion_view

app_name = "cotizaciones"

urlpatterns = [
    path("", CotizacionListView.as_view(), name="cotizacion-list"),
    path("crear/", CotizacionCreateView.as_view(), name="cotizacion-create"),
    path("convertir/", buscar_cotizacion_view, name="cotizacion-buscar"),
    path("<int:pk>/convertir/", convertir_cotizacion_view, name="cotizacion-convertir"),
]
