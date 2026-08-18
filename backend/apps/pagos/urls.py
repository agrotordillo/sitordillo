from django.urls import path

from .views.cuenta_views import CuentaPorPagarListView, generar_cuenta_view
from .views.pago_views import registrar_pago_view

app_name = "pagos"

urlpatterns = [
    path("", CuentaPorPagarListView.as_view(), name="cuenta-list"),
    path("ordenes/<int:pk>/generar/", generar_cuenta_view, name="cuenta-generar"),
    path("<int:pk>/pagar/", registrar_pago_view, name="pago-registrar"),
]
