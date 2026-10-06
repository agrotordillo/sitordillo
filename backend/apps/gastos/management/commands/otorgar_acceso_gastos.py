"""Otorga las capacidades de Gastos a un usuario desde el servidor.

Dentro del sistema solo puede dar acceso a Gastos quien ya lo tiene (ver
apps.core.permisos_estrictos). Este comando es la salida para cuando nadie
con acceso está disponible (o para dar el acceso inicial en una instalación
donde no existe el usuario "admin"); queda registrado en la bitácora como
hecho desde el servidor.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.permisos_estrictos import grupos_protegidos
from apps.gastos.models import BitacoraAccesoGastos


class Command(BaseCommand):
    help = "Otorga a un usuario las capacidades del módulo de Gastos (todas, o solo las indicadas con --grupo)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--grupo",
            action="append",
            dest="grupos",
            help="Nombre de la capacidad a otorgar; se puede repetir. Sin esta opción se otorgan todas las de Gastos.",
        )
        parser.add_argument("--nota", default="Otorgado desde el servidor.", help="Motivo, para la bitácora.")

    def handle(self, *args, username, grupos, nota, **options):
        usuario = get_user_model().objects.filter(username=username).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario «{username}».")

        disponibles = grupos_protegidos()
        if grupos:
            seleccion = list(disponibles.filter(name__in=grupos))
            faltantes = set(grupos) - {g.name for g in seleccion}
            if faltantes:
                validos = ", ".join(sorted(g.name for g in disponibles))
                raise CommandError(f"No son capacidades de Gastos: {', '.join(sorted(faltantes))}. Válidas: {validos}.")
        else:
            seleccion = list(disponibles)

        with transaction.atomic():
            antes = set(usuario.groups.filter(pk__in=[g.pk for g in seleccion]))
            usuario.groups.add(*seleccion)
            BitacoraAccesoGastos.registrar_cambios(usuario, antes, antes | set(seleccion), nota=nota)

        nuevas = sorted(g.name for g in set(seleccion) - antes)
        if nuevas:
            self.stdout.write(self.style.SUCCESS(f"Otorgado a {username}: {', '.join(nuevas)}."))
        else:
            self.stdout.write(f"{username} ya tenía esas capacidades; no se hizo ningún cambio.")
