"""Archivos que suben los usuarios (MEDIA): validación al recibirlos,
nombres no adivinables al guardarlos y descarga solo con permiso.

Ningún archivo subido se sirve como estático público: /media/ pasa por
apps.core.views.servir_archivo_protegido, que solo entrega un archivo si
algún registro registrado aquí lo tiene en su campo y el usuario puede ver
ese registro (B11 en docs/AUDITORIA.md). Cada módulo declara sus propios
archivos en el ready() de su AppConfig con registrar_archivo_protegido();
un archivo que ningún registro reconoce no se sirve."""

import os
import uuid
from dataclasses import dataclass
from typing import Callable

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.deconstruct import deconstructible

MEGABYTE = 1024 * 1024


# --- Nombres de archivo -------------------------------------------------

@deconstructible
class RutaAleatoria:
    """upload_to que guarda cada archivo en `<carpeta>/<uuid>/<nombre>`: la
    ruta no se puede adivinar ni chocar con la de otro archivo, y el
    nombre original se conserva para que la descarga se llame igual que lo
    que subió el usuario."""

    def __init__(self, carpeta):
        self.carpeta = carpeta.strip("/")

    def __call__(self, instance, filename):
        return f"{self.carpeta}/{uuid.uuid4().hex}/{os.path.basename(filename)}"

    def __eq__(self, other):
        return isinstance(other, RutaAleatoria) and other.carpeta == self.carpeta

    def __hash__(self):
        return hash(self.carpeta)


# --- Validación al subir ------------------------------------------------

# Firma inicial de cada tipo permitido: la extensión sola la decide quien
# sube el archivo; los primeros bytes confirman que de verdad es eso.
FIRMAS = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".xml": (b"<", b"\xef\xbb\xbf<"),
}
EXTENSIONES_COMPROBANTE = frozenset(FIRMAS)
TIPOS_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".xml": "application/xml",
}


def validar_archivo(archivo, extensiones=EXTENSIONES_COMPROBANTE, max_bytes=10 * MEGABYTE):
    """Lanza forms.ValidationError si `archivo` no es de un tipo permitido
    (por extensión y por contenido) o rebasa `max_bytes`."""
    nombre = os.path.basename(archivo.name or "")
    extension = os.path.splitext(nombre)[1].lower()
    if extension not in extensiones:
        permitidas = ", ".join(sorted(e.lstrip(".").upper() for e in extensiones))
        raise forms.ValidationError(f'"{nombre}" no es un tipo de archivo permitido ({permitidas}).')
    if archivo.size > max_bytes:
        raise forms.ValidationError(f'"{nombre}" pesa más de {max_bytes // MEGABYTE} MB.')

    archivo.seek(0)
    inicio = archivo.read(16).lstrip(b" \t\r\n")
    archivo.seek(0)
    if extension in FIRMAS and not inicio.startswith(FIRMAS[extension]):
        raise forms.ValidationError(f'"{nombre}" no es un {extension.lstrip(".").upper()} válido.')


ACCEPT_COMPROBANTE = ",".join(sorted(EXTENSIONES_COMPROBANTE))


class ComprobanteFormMixin:
    """Para formularios con un campo `comprobante` (pagos, cobros, gastos):
    solo acepta PDF, XML, JPG o PNG de hasta 10 MB, revisados también por
    contenido (B32 en docs/AUDITORIA.md, decisión del usuario: las mismas
    reglas que los adjuntos del correo de pagos). Solo se valida un archivo
    recién subido: el que el registro ya tenía guardado, o "quitarlo", pasa
    tal cual, así que editar un registro viejo no exige volver a subirlo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comprobante"].widget.attrs.setdefault("accept", ACCEPT_COMPROBANTE)

    def clean_comprobante(self):
        archivo = self.cleaned_data.get("comprobante")
        if isinstance(archivo, UploadedFile):
            validar_archivo(archivo)
        return archivo


def tipo_mime(nombre):
    """El tipo MIME según la extensión ya validada -nunca el que declara el
    navegador al subir el archivo, que lo decide quien sube-."""
    return TIPOS_MIME.get(os.path.splitext(nombre)[1].lower(), "application/octet-stream")


# --- Registro de archivos protegidos ------------------------------------

@dataclass(frozen=True)
class ArchivoProtegido:
    prefijo: str
    campo: str
    # Queryset de los registros que `user` puede ver; ya incluye el chequeo
    # de permiso y de sucursal del módulo dueño.
    visibles: Callable


_REGISTRO = []


def registrar_archivo_protegido(prefijo, campo, visibles):
    """Declara que los archivos guardados bajo `prefijo` (la carpeta de su
    upload_to) pertenecen al `campo` de los registros que devuelve
    `visibles(user)`. Se llama desde el ready() de la AppConfig dueña."""
    prefijo = prefijo.strip("/") + "/"
    if not any(r.prefijo == prefijo for r in _REGISTRO):
        _REGISTRO.append(ArchivoProtegido(prefijo, campo, visibles))


def puede_descargar(user, ruta):
    """True si algún registro visible para `user` tiene exactamente este
    archivo. Sin registro que lo reconozca, nadie lo descarga."""
    for registro in sorted(_REGISTRO, key=lambda r: len(r.prefijo), reverse=True):
        if ruta.startswith(registro.prefijo):
            return registro.visibles(user).filter(**{registro.campo: ruta}).exists()
    return False
