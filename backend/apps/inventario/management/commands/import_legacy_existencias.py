"""Carga el inventario inicial de sitordillo con las existencias de scv_web
(el sistema anterior) a la fecha de corte, desde datos/scv_web/existencias.tsv
que genera exportar_scv_web.

Decisiones del usuario (2026-10-27):
  - Un lote por producto y almacén (numero_lote "INICIAL"), con fecha de
    ingreso al corte y el costo actual del catálogo de scv_web -el mismo que
    muestra su reporte de existencias-; si ahí no tiene costo, el de catálogo
    de sitordillo. Su movimiento de inventario es un AJUSTE (como cualquier
    entrada que no es compra, ver inventario.services.aplicar_movimiento_almacen),
    así el kardex arranca desde ahí.
  - La existencia del 02 BODEGA SUR va a la sucursal BODEGA SUR y la de cada
    móvil a su móvil (ver scv_web.Almacenes.de_existencia).
  - Las existencias negativas o en cero de scv_web no se cargan.
  - Corte: el día de la copia de scv_web. El proceso se repite al salir a
    producción, sobre una base sin inventario: si ya hay lotes, el comando se
    niega, porque sumaría la misma mercancía dos veces. Con --completar
    agrega solo los productos y almacenes que faltaron, mientras el inventario
    siga siendo solo el inicial (sin ninguna operación encima).
"""
from datetime import datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core import scv_web
from apps.core.scv_web import DOS, decimal, texto
from apps.inventario.models import Lote, MovimientoInventario, redondear_costo
from apps.products.models import Producto

COLUMNAS = ["almacen", "codigo", "existencia", "costo"]
NUMERO_LOTE = "INICIAL"


class Command(BaseCommand):
    help = "Carga el inventario inicial con las existencias de scv_web (datos/scv_web/existencias.tsv)."

    def add_arguments(self, parser):
        parser.add_argument("--corte", required=True, help="Fecha de corte (AAAA-MM-DD): la de la copia de scv_web.")
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo valida y reporta.")
        parser.add_argument("--directorio", default=str(scv_web.DATA_DIR))
        parser.add_argument(
            "--completar", action="store_true",
            help="Sobre un inventario inicial ya cargado, agrega solo lo que faltó (p. ej. productos que no "
            "existían y se dieron de alta con import_legacy_productos --solo-nuevos). Solo si todavía no hubo "
            "ninguna operación de inventario.",
        )

    def handle(self, *args, **options):
        try:
            corte = datetime.strptime(options["corte"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("--corte debe ser una fecha AAAA-MM-DD.") from exc
        dry_run = options["dry_run"]
        ya_cargados, siguiente = set(), 1
        if Lote.objects.exists():
            if not options["completar"]:
                raise CommandError(
                    "Ya hay inventario en sitordillo: el inventario inicial solo se carga sobre una base sin lotes "
                    "(sumaría la misma mercancía dos veces). Para agregar solo lo que faltó, usa --completar."
                )
            if (
                Lote.objects.exclude(numero_lote=NUMERO_LOTE).exists()
                or MovimientoInventario.objects.exclude(folio__startswith="MOVI-").exists()
            ):
                raise CommandError(
                    "Ya hubo operaciones sobre el inventario (ventas, compras, traspasos o ajustes): el inventario "
                    "inicial ya no se puede completar desde scv_web; captura lo que falte con un movimiento de almacén."
                )
            ya_cargados = set(Lote.objects.values_list("almacen_id", "producto_id"))
            siguiente = Lote.objects.filter(folio__startswith="LOTI-").count() + 1

        try:
            with transaction.atomic():
                almacenes = scv_web.Almacenes(crear=not dry_run)
            filas = list(scv_web.leer_tsv(options["directorio"], "existencias", COLUMNAS))
        except (ValueError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc

        productos = {p.sku: p for p in Producto.objects.only("pk", "sku", "precio_costo")}
        fecha_movimiento = datetime.combine(corte, time(23, 59, 59), tzinfo=scv_web.ZONA)
        motivo = f"Inventario inicial: existencia de scv_web al {corte:%d/%m/%Y}"
        stats = {
            "lotes": 0, "sin_existencia": 0, "sin_producto": 0, "valor_sin_producto": Decimal("0"),
            "costo_de_sitordillo": 0, "ya_cargados": 0,
        }
        errores, por_almacen, lotes = [], {}, []
        for fila in filas:
            cantidad = decimal(fila["existencia"])
            if cantidad is None or cantidad <= 0:
                # Negativa en scv_web, o menos de un centésimo: nada que cargar.
                stats["sin_existencia"] += 1
                continue
            costo_legado = decimal(fila["costo"], Decimal("0.0001")) or Decimal("0")
            producto = productos.get(texto(fila["codigo"]))
            if producto is None:
                stats["sin_producto"] += 1
                stats["valor_sin_producto"] += (cantidad * costo_legado).quantize(DOS)
                continue
            try:
                almacen = almacenes.de_existencia(fila["almacen"])
            except KeyError:
                errores.append(f"{fila['codigo']}: almacén {fila['almacen']!r} sin equivalente en sitordillo")
                continue
            if (getattr(almacen, "pk", None), producto.pk) in ya_cargados:
                stats["ya_cargados"] += 1
                continue
            if costo_legado <= 0:
                stats["costo_de_sitordillo"] += 1
            costo = redondear_costo(costo_legado if costo_legado > 0 else producto.precio_costo)
            n = siguiente + len(lotes)
            lotes.append(Lote(
                folio=f"LOTI-{n:06d}", slug=f"inventario-inicial-{n}", producto=producto, almacen=almacen,
                numero_lote=NUMERO_LOTE, fecha_ingreso=corte, costo_unitario=costo,
                cantidad_inicial=cantidad, cantidad_disponible=cantidad,
            ))
            nombre = getattr(almacen, "nombre", fila["almacen"])
            resumen = por_almacen.setdefault(nombre, [0, Decimal("0"), Decimal("0")])
            resumen[0] += 1
            resumen[1] += cantidad
            resumen[2] += (cantidad * costo).quantize(DOS)

        stats["lotes"] = len(lotes)
        if errores:
            for error in errores[:20]:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            raise CommandError(f"{len(errores)} existencias sin almacén en sitordillo: no se cargó nada.")

        if not dry_run:
            with transaction.atomic():
                creados = Lote.objects.bulk_create(lotes, batch_size=1000)
                MovimientoInventario.objects.bulk_create(
                    [
                        MovimientoInventario(
                            folio=f"MOVI-{n:06d}", slug=f"inventario-inicial-{n}", lote=lote,
                            tipo=MovimientoInventario.Tipo.AJUSTE, cantidad=lote.cantidad_inicial,
                            cantidad_anterior=Decimal("0.00"), cantidad_nueva=lote.cantidad_inicial,
                            motivo=motivo, fecha_movimiento=fecha_movimiento,
                        )
                        for n, lote in enumerate(creados, start=siguiente)
                    ],
                    batch_size=1000,
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
        if almacenes.creados:
            accion = "Se crearían" if dry_run else "Se crearon"
            self.stdout.write(f"{accion} {len(almacenes.creados)} almacenes inactivos: " + "; ".join(almacenes.creados))
        for nombre, (n, unidades, valor) in sorted(por_almacen.items()):
            self.stdout.write(f"  {nombre:24} lotes={n:5,} unidades={unidades:>12,.2f} valor=${valor:>14,.2f}")
        total = sum((v for _, _, v in por_almacen.values()), Decimal("0"))
        self.stdout.write(self.style.SUCCESS(
            f"Lotes de inventario inicial={stats['lotes']:,} valor=${total:,.2f} (corte {corte:%d/%m/%Y})"
        ))
        self.stdout.write(
            f"Omitidas: existencia negativa o en cero={stats['sin_existencia']} · "
            f"productos que no existen en sitordillo={stats['sin_producto']} (${stats['valor_sin_producto']:,.2f}) · "
            f"con costo de sitordillo por no tener en scv_web={stats['costo_de_sitordillo']}"
            + (f" · ya estaban cargadas={stats['ya_cargados']}" if ya_cargados else "")
        )
