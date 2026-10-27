"""Importa el historial de compras de scv_web (el sistema anterior) desde los
TSV de datos/scv_web/ que genera exportar_scv_web (ver apps.core.scv_web).

En scv_web la compra de mercancía es un gasto de la cuenta 2999 "MATERIALES
PARA VENTA (ALMACEN)" con sus renglones de producto. Reglas, decididas con el
usuario en la evaluación del 2026-10-26:
  - Cada compra llega como una OrdenCompra ya Recibida (lo recibido = lo
    pedido), sin lotes, movimientos de inventario ni cuenta por pagar.
  - El precio de cada renglón es el de scv_web, que ya viene neto: en muchas
    compras el subtotal del encabezado es el bruto y el descuento no quedó
    guardado en ninguna columna. Por eso descuento y descuento base van en 0
    y el total se rearma con los renglones + IVA + IEPS - retenciones; la
    diferencia contra el total de scv_web se reporta.
  - Las compras del 02 BODEGA SUR van al CEDIS (ver scv_web.Almacenes).
  - Es repetible: las compras ya importadas (OrdenCompra.id_legado) se saltan,
    pero se les agregan los renglones que se habían omitido porque su producto
    no existía y ya existe (OrdenCompraDetalle con folio OCD-L<id del renglón>).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.core import scv_web
from apps.core.scv_web import CUATRO, DOS, decimal, texto

COLUMNAS_COMPRA = [
    "id", "fecha", "id_proveedor", "almacen", "referencia", "estado_pago", "medio_pago", "clave_sat",
    "es_fiscal", "iva", "ieps", "retencion_iva", "retencion_isr", "total", "observaciones",
]
COLUMNAS_PRODUCTO = ["id", "id_documento", "codigo", "cantidad", "valor_unitario", "importe"]
LOTE = 500


class Command(BaseCommand):
    help = "Importa las compras históricas de scv_web desde datos/scv_web/*.tsv (ver exportar_scv_web)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo valida y reporta.")
        parser.add_argument("--directorio", default=str(scv_web.DATA_DIR))

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.directorio = options["directorio"]
        self.stats = {
            "compras": 0, "ya_importadas": 0, "renglones": 0, "sin_proveedor": 0, "sin_renglones": 0,
            "renglones_sin_producto": 0, "importe_sin_producto": Decimal("0"), "precio_desde_importe": 0,
            "con_diferencia": 0, "diferencia_total": Decimal("0"),
        }
        self.errores = []
        try:
            with transaction.atomic():
                self.almacenes = scv_web.Almacenes(crear=not self.dry_run)
            self.proveedores = scv_web.ProveedoresLegado(
                scv_web.leer_asociados(self.directorio), crear=not self.dry_run
            )
        except (ValueError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc
        self.productos = scv_web.productos_por_sku()
        self.formas_pago = scv_web.formas_pago_por_clave()
        importadas = dict(OrdenCompra.objects.exclude(id_legado=None).values_list("id_legado", "pk"))
        renglones_importados = set(
            OrdenCompraDetalle.objects.filter(folio__startswith="OCD-L").values_list("folio", flat=True)
        )

        productos = scv_web.Emparejador(scv_web.agrupar_por(
            scv_web.leer_tsv(self.directorio, "compras_productos", COLUMNAS_PRODUCTO), "id_documento"
        ))
        lote, faltantes = [], []
        for fila in scv_web.leer_tsv(self.directorio, "compras", COLUMNAS_COMPRA):
            renglones = productos.de(int(fila["id"]))
            if int(fila["id"]) in importadas:
                self.stats["ya_importadas"] += 1
                # Renglones que se omitieron al importarla porque su producto
                # todavía no existía en sitordillo (ver
                # import_legacy_productos --solo-nuevos): se completan ahora.
                pendientes = [r for r in renglones if f"OCD-L{r['id']}" not in renglones_importados]
                for detalle in self._renglones(pendientes, contar=False):
                    detalle.orden_compra_id = importadas[int(fila["id"])]
                    faltantes.append(detalle)
                continue
            armada = self._armar(fila, renglones)
            if armada is not None:
                lote.append(armada)
            if len(lote) >= LOTE:
                self._guardar(lote)
                lote = []
        if lote:
            self._guardar(lote)
        self.stats["renglones_completados"] = len(faltantes)
        if faltantes and not self.dry_run:
            OrdenCompraDetalle.objects.bulk_create(faltantes)
        self._reportar()

    def _renglones(self, renglones, contar=True):
        """Los OrdenCompraDetalle (sin orden) de los renglones de scv_web que
        se pueden importar. `contar`: si se suman a las estadísticas de lo
        omitido (no, al completar una compra ya importada)."""
        detalles = []
        for r in renglones:
            producto_id = self.productos.get(texto(r["codigo"]))
            cantidad = decimal(r["cantidad"])
            importe = decimal(r["importe"]) or Decimal("0")
            if producto_id is None or not cantidad or cantidad <= 0:
                if contar:
                    self.stats["renglones_sin_producto"] += 1
                    self.stats["importe_sin_producto"] += importe
                continue
            precio = decimal(r["valor_unitario"], CUATRO) or Decimal("0")
            if abs(cantidad * precio - importe) > 1:
                # El valor unitario mal capturado (p. ej. PANACUR a $36,000 en
                # vez de $36): el importe del renglón es el que cuadra con el
                # subtotal de la compra.
                if contar:
                    self.stats["precio_desde_importe"] += 1
                precio = (importe / cantidad).quantize(CUATRO)
            detalles.append(OrdenCompraDetalle(
                folio=f"OCD-L{r['id']}", slug=f"ocd-l{r['id']}", producto_id=producto_id,
                cantidad=cantidad, precio_unitario=precio, cantidad_recibida=cantidad,
            ))
        return detalles

    def _armar(self, fila, renglones):
        proveedor_id = self.proveedores.pk_de(int(fila["id_proveedor"]))
        if proveedor_id is None:
            self.stats["sin_proveedor"] += 1
            return None
        try:
            almacen = self.almacenes.de_compra(fila["almacen"])
        except KeyError:
            self.errores.append(f"compra {fila['id']}: almacén {fila['almacen']!r} sin equivalente")
            return None

        detalles = self._renglones(renglones)
        if not detalles:
            self.stats["sin_renglones"] += 1
            return None

        medio = (fila["medio_pago"] or "").lower()
        orden = OrdenCompra(
            folio=f"OC-L{fila['id']}", slug=f"oc-l{fila['id']}", id_legado=int(fila["id"]),
            proveedor_id=proveedor_id, almacen_destino=almacen,
            fecha_orden=scv_web.fecha_hora(fila["fecha"]).date(),
            estatus=OrdenCompra.Estatus.RECIBIDA, es_fiscal=fila["es_fiscal"] == "SI",
            documento=texto(fila["referencia"], 50),
            estado_pago=OrdenCompra.EstadoPago.CREDITO if fila["estado_pago"] == "CREDITO" else OrdenCompra.EstadoPago.CONTADO,
            medio_pago=medio if medio in OrdenCompra.MedioPago.values else OrdenCompra.MedioPago.INDEFINIDO,
            forma_pago_id=self.formas_pago.get(fila["clave_sat"]),
            # bulk_create no pasa por OrdenCompra.save(), que congelaría aquí el
            # descuento actual del proveedor: el precio de scv_web ya es neto.
            descuento_pct=Decimal("0.00"), descuento_base_pct=Decimal("0.00"),
            iva=decimal(fila["iva"]) or Decimal("0.00"), ieps=decimal(fila["ieps"]) or Decimal("0.00"),
            retencion_iva=decimal(fila["retencion_iva"]) or Decimal("0.00"),
            retencion_isr=decimal(fila["retencion_isr"]) or Decimal("0.00"),
            observaciones=texto(fila["observaciones"]),
        )
        total = (
            sum(((d.cantidad * d.precio_unitario).quantize(DOS) for d in detalles), Decimal("0.00"))
            + orden.iva + orden.ieps - orden.retencion_iva - orden.retencion_isr
        )
        diferencia = abs(total - decimal(fila["total"]))
        if diferencia >= 1:
            self.stats["con_diferencia"] += 1
            self.stats["diferencia_total"] += diferencia
        return orden, detalles

    def _guardar(self, lote):
        self.stats["compras"] += len(lote)
        self.stats["renglones"] += sum(len(detalles) for _, detalles in lote)
        if self.dry_run:
            return
        with transaction.atomic():
            ordenes = OrdenCompra.objects.bulk_create([orden for orden, _ in lote])
            detalles = []
            for orden, (_, sus_detalles) in zip(ordenes, lote):
                for detalle in sus_detalles:
                    detalle.orden_compra = orden
                detalles.extend(sus_detalles)
            OrdenCompraDetalle.objects.bulk_create(detalles, batch_size=5000)
        self.stdout.write(f"  ... {self.stats['compras']:,} compras")

    def _reportar(self):
        s = self.stats
        if self.dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
        if self.almacenes.creados:
            accion = "Se crearían" if self.dry_run else "Se crearon"
            self.stdout.write(f"{accion} {len(self.almacenes.creados)} almacenes inactivos: "
                              + "; ".join(self.almacenes.creados))
        self.stdout.write(f"Proveedores: {self.proveedores.resultado}")
        self.stdout.write(self.style.SUCCESS(
            f"Compras={s['compras']:,} renglones={s['renglones']:,} (ya importadas antes: {s['ya_importadas']:,}; "
            f"renglones que se les completaron: {s['renglones_completados']:,})"
        ))
        self.stdout.write(
            f"Omitidas: sin proveedor={s['sin_proveedor']} sin renglones importables={s['sin_renglones']} · "
            f"renglones sin producto en sitordillo={s['renglones_sin_producto']} (${s['importe_sin_producto']:,.2f}) · "
            f"renglones con precio tomado del importe={s['precio_desde_importe']} · "
            f"compras cuyo total no cuadra con scv_web={s['con_diferencia']} (${s['diferencia_total']:,.2f})"
        )
        for error in [*self.proveedores.errores, *self.errores][:40]:
            self.stdout.write(self.style.WARNING(f"  - {error}"))
