from django.utils.http import url_has_allowed_host_and_scheme


def url_de_regreso(request, por_defecto):
    """El `next` del POST (o del GET) para regresar a donde estaba el
    usuario, solo si apunta a este mismo sitio; si no, `por_defecto`.

    Sin esta validación un enlace preparado mandaba al usuario, después de
    guardar, a un sitio externo -o pintaba un "Cancelar" con un
    `javascript:`- (B12 en docs/AUDITORIA.md). Es la misma regla que usa
    el login de Django para su propio `next`."""
    for candidato in (request.POST.get("next"), request.GET.get("next")):
        if candidato and url_has_allowed_host_and_scheme(
            candidato, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return candidato
    return str(por_defecto)
