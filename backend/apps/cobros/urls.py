from django.urls import path

from .views.cuenta_views import CuentaPorCobrarListView
from .views.cobro_views import registrar_cobro_view

app_name = "cobros"

urlpatterns = [
    path("", CuentaPorCobrarListView.as_view(), name="cuenta-list"),
    path("<int:pk>/cobrar/", registrar_cobro_view, name="cobro-registrar"),
]
