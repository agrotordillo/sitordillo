from django.urls import path

from .views.traspaso_views import (
    TraspasoCreateView,
    TraspasoListView,
    traspaso_enviar_view,
    traspaso_recibir_view,
)

app_name = "traspasos"

urlpatterns = [
    path("", TraspasoListView.as_view(), name="traspaso-list"),
    path("crear/", TraspasoCreateView.as_view(), name="traspaso-create"),
    path("<int:pk>/enviar/", traspaso_enviar_view, name="traspaso-enviar"),
    path("<int:pk>/recibir/", traspaso_recibir_view, name="traspaso-recibir"),
]
