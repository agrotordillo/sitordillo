"""Protección contra doble envío de formularios que crean operaciones (B15
y B16 en docs/AUDITORIA.md).

Cada formulario protegido lleva un token de un solo uso
(`{% token_envio %}`, ver core_extras). La vista lo usa así:

    if (url := envio_ya_procesado(request)):
        return respuesta_envio_duplicado(request, url)        # vía rápida
    ...validar...
    try:
        with transaction.atomic():
            envio = reservar_envio(request)                    # primera línea
            ...guardar la operación...
            envio.completar(url_del_resultado)
    except EnvioDuplicado as duplicado:
        return respuesta_envio_duplicado(request, duplicado.url_resultado, por_defecto)

La reserva es un INSERT con el token como llave primaria dentro de la
transacción del guardado: un segundo envío simultáneo espera en ese INSERT
a que el primero termine; si el primero confirmó, choca y se le manda al
resultado ya creado; si el primero se revirtió, procede normalmente. Un
formulario sin token (una pestaña vieja en caché) se procesa como siempre,
sin esta protección."""

import uuid

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect

from apps.core.models import EnvioUnico

CAMPO_TOKEN = "token_envio"


class EnvioDuplicado(Exception):
    def __init__(self, url_resultado=""):
        super().__init__("Este formulario ya se había enviado.")
        self.url_resultado = url_resultado


class Envio:
    def __init__(self, registro=None):
        self.registro = registro

    def completar(self, url_resultado):
        """Guarda a dónde mandar a un envío repetido. Se llama al final, dentro
        de la misma transacción del guardado."""
        if self.registro is not None:
            EnvioUnico.objects.filter(pk=self.registro.pk).update(url_resultado=str(url_resultado)[:500])


def token_del_post(request):
    try:
        return uuid.UUID(request.POST.get(CAMPO_TOKEN, ""))
    except (TypeError, ValueError):
        return None


def envio_ya_procesado(request):
    """Vía rápida, antes de validar nada: si este token ya se usó con
    éxito, la URL de su resultado; si no, None."""
    token = token_del_post(request)
    if token is None:
        return None
    return (
        EnvioUnico.objects.filter(token=token, usuario=request.user)
        .exclude(url_resultado="")
        .values_list("url_resultado", flat=True)
        .first()
    )


def reservar_envio(request):
    """Reserva el token del formulario. Debe llamarse dentro de la
    transaction.atomic() que guarda la operación. Lanza EnvioDuplicado si
    otro envío con el mismo token ya se guardó."""
    token = token_del_post(request)
    if token is None:
        return Envio()
    try:
        with transaction.atomic():
            return Envio(EnvioUnico.objects.create(token=token, usuario=request.user, ruta=request.path[:255]))
    except IntegrityError:
        previo = EnvioUnico.objects.filter(token=token, usuario=request.user).first()
        raise EnvioDuplicado(previo.url_resultado if previo else "")


def respuesta_envio_duplicado(request, url_resultado, por_defecto="home"):
    messages.info(request, "Esta operación ya se había registrado; no se volvió a guardar.")
    return redirect(url_resultado or por_defecto)


class EnvioUnicoMixin:
    """Vía rápida para CreateView/UpdateView: un envío ya guardado no se
    vuelve a validar, se manda directo a su resultado. La vista además
    llama a reservar_envio() como primera línea de la transaction.atomic()
    de su form_valid() y atrapa EnvioDuplicado."""

    def post(self, request, *args, **kwargs):
        url = envio_ya_procesado(request)
        if url:
            return respuesta_envio_duplicado(request, url)
        return super().post(request, *args, **kwargs)
