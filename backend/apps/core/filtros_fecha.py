"""Filtro de fecha "se ve hoy por default" compartido por las listas que
pivotan sobre una fecha propia del modelo (Venta.fecha_venta,
Cotizacion.fecha_cotizacion, Pedido.fecha_pedido): sin nada en la URL se
ve el día de hoy; para ver otro día, se navega a esa fecha -nunca hay que
"limpiar" un filtro para volver a ver algo-. Mismo patrón de dos formas de
uso que apps.core.filtros_producto: funciones sueltas o FiltroFechaMixin."""

from datetime import timedelta

from django.utils import timezone

from apps.core.parametros import fecha_filtro, url_con_fecha


def contexto_filtro_fecha(request, fecha_seleccionada, *, param="fecha"):
    """Arma, en un dict, lo que necesita el template compartido
    `core/includes/_filtro_fecha.html`: la fecha activa y los enlaces de
    día anterior/siguiente/hoy -cada uno con cualquier otro filtro ya
    presente en la querystring preservado (ver url_con_fecha)-."""
    hoy = timezone.localdate()
    return {
        "fecha_filtro": fecha_seleccionada,
        "fecha_hoy": hoy,
        "url_fecha_anterior": url_con_fecha(request, fecha_seleccionada - timedelta(days=1), param=param),
        "url_fecha_siguiente": url_con_fecha(request, fecha_seleccionada + timedelta(days=1), param=param),
        "url_fecha_hoy": url_con_fecha(request, hoy, param=param),
    }


class FiltroFechaMixin:
    """Mixin para ListView. Configúralo con:

    - filtro_fecha_campo: el DateTimeField del modelo a filtrar (obligatorio).
    - filtro_fecha_param: nombre del parámetro GET (por defecto "fecha").

    get_context_data() agrega el filtro solo, vía la cadena de super()
    (igual que FiltrosProductoMixin). get_queryset() NO se sobreescribe
    aquí a propósito -algunas vistas (p. ej. PedidoListView) arman su
    queryset base sin pasar por super().get_queryset()-: cada vista llama
    self.aplicar_filtro_fecha(queryset) donde le corresponda."""

    filtro_fecha_campo = None
    filtro_fecha_param = "fecha"

    def get_fecha_filtro(self):
        if not hasattr(self, "_fecha_filtro_cache"):
            self._fecha_filtro_cache = fecha_filtro(self.request, param=self.filtro_fecha_param)
        return self._fecha_filtro_cache

    def aplicar_filtro_fecha(self, queryset):
        return queryset.filter(**{f"{self.filtro_fecha_campo}__date": self.get_fecha_filtro()})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(contexto_filtro_fecha(self.request, self.get_fecha_filtro(), param=self.filtro_fecha_param))
        return context
