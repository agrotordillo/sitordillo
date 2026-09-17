"""Consolida clientes con el mismo nombre exacto (mayúsculas, espacios
recortados y colapsados): deja uno solo y borra los demás.

A diferencia de merge_clientes_duplicados_rfc (que cruza contra el RFC del
sistema anterior para estar seguro de que es la misma persona), aquí el
único criterio es el nombre idéntico -pedido explícito: "si encuentra
duplicados en los nombres, igual elimina los que sean iguales"-. Es más
arriesgado (dos clientes distintos podrían compartir nombre por
coincidencia), pero Cliente.ventas/cotizaciones usan on_delete=PROTECT: si
alguno de los duplicados ya tiene una venta o cotización real, Django
rechaza su borrado y se reporta para revisión manual en vez de forzarlo.

De cada grupo se conserva el que tenga lista_precio asignado (si solo uno
la tiene) o, si no hay forma de distinguirlos por eso, el de id más bajo
-el primero importado-."""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import ProtectedError

from apps.clientes.models import Cliente


def norm_nombre(valor):
    return re.sub(r"\s+", " ", (valor or "").strip().upper())


class Command(BaseCommand):
    help = "Borra clientes con el mismo nombre exacto, dejando uno solo por grupo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Borra de verdad; sin esta bandera solo reporta (dry-run, comportamiento por default).",
        )

    def handle(self, *args, **options):
        aplicar = options["apply"]

        clientes = list(Cliente.objects.all().only("id", "nombre", "lista_precio_id"))
        grupos = defaultdict(list)
        for c in clientes:
            nombre = norm_nombre(c.nombre)
            if nombre:
                grupos[nombre].append(c)
        grupos = {k: v for k, v in grupos.items() if len(v) > 1}

        casos = []
        for nombre, miembros in grupos.items():
            miembros = sorted(miembros, key=lambda c: c.id)
            con_lista = [c for c in miembros if c.lista_precio_id]
            conservar = con_lista[0] if len(con_lista) == 1 else miembros[0]
            a_borrar = [c.id for c in miembros if c.id != conservar.id]
            casos.append((nombre, conservar.id, a_borrar))

        total_a_borrar = sum(len(a_borrar) for _, _, a_borrar in casos)
        self.stdout.write(f"Nombres duplicados: {len(casos)} · clientes a borrar: {total_a_borrar}")

        if not aplicar:
            for nombre, conservar, a_borrar in casos:
                self.stdout.write(f"  - {nombre!r} conserva id={conservar} borra={a_borrar}")
            self.stdout.write(self.style.WARNING(
                f"Dry-run: se borrarían {total_a_borrar} clientes. Corre con --apply para aplicar."
            ))
            return

        borrados, protegidos = 0, []
        for nombre, conservar, a_borrar in casos:
            for cid in a_borrar:
                try:
                    Cliente.objects.get(pk=cid).delete()
                    borrados += 1
                except ProtectedError:
                    protegidos.append((nombre, conservar, cid))
                except Cliente.DoesNotExist:
                    continue

        self.stdout.write(self.style.SUCCESS(f"Listo. {borrados} clientes duplicados borrados."))
        if protegidos:
            self.stdout.write(self.style.WARNING(
                f"{len(protegidos)} no se pudieron borrar por tener ventas/cotizaciones (revisión manual):"
            ))
            for nombre, conservar, cid in protegidos:
                self.stdout.write(f"  - {nombre!r} conservado={conservar} con historial (no borrado)={cid}")
