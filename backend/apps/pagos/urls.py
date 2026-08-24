from django.urls import path

from .views.cuenta_views import CuentaPorPagarListView, generar_cuenta_view
from .views.pago_views import (
    enviar_comprobante_email_view,
    preparar_pago_multiple_view,
    registrar_pago_multiple_view,
    registrar_pago_view,
)

app_name = "pagos"

urlpatterns = [
    path("", CuentaPorPagarListView.as_view(), name="cuenta-list"),
    path("ordenes/<int:pk>/generar/", generar_cuenta_view, name="cuenta-generar"),
    path("<int:pk>/pagar/", registrar_pago_view, name="pago-registrar"),
    path("pagar-varias/preparar/", preparar_pago_multiple_view, name="pago-multiple-preparar"),
    path("pagar-varias/registrar/", registrar_pago_multiple_view, name="pago-multiple-registrar"),
    path("pagos/<int:pk>/enviar-correo/", enviar_comprobante_email_view, name="pago-enviar-correo"),
]
