"""Importa el historial de ventas de scv_web (el sistema anterior) desde los
TSV de datos/scv_web/ que genera exportar_scv_web (ver apps.core.scv_web).

Reglas, decididas con el usuario en la evaluación del 2026-10-26:
  - Se importan las notas de venta y remisiones no canceladas, y las notas de
    devolución activas. Las facturas no (agrupan notas ya importadas).
  - Una venta histórica no mueve inventario, no genera cuenta por cobrar ni
    factura y no tiene turno: solo sirve para reportes y análisis.
  - Cada renglón guarda el costo con el que salió ese día
    (VentaDetalle.costo_unitario), salvo los costos mal capturados en el
    sistema anterior (más de COSTO_ANOMALO_VECES el precio sin impuesto, p.
    ej. PANACUR a $36,000 por pieza), que se dejan vacíos para que el análisis
    use el costo de catálogo.
  - precio_unitario es el precio final con impuestos (total / cantidad) y sin
    descuento, porque en scv_web el precio ya viene neto. La cantidad se
    redondea a 2 decimales (scv_web usa 3).
  - Un solo pago va en Venta.forma_pago; varios, en VentaPago.
  - El vendedor de scv_web (documento.id_vendedor) queda en Venta.created_by,
    que es a quien los reportes de comisiones le atribuyen la venta; cada
    vendedor es un usuario inactivo (ver scv_web.VendedoresLegado).
    --solo-vendedores lo asigna a las ventas que ya estaban importadas.
  - Es repetible: las ventas cuyo id ya se importó (Venta.id_legado) se saltan,
    así que se puede volver a exportar e importar para traer lo más reciente;
    a esas se les agregan los renglones que se habían omitido porque su
    producto no existía y ya existe (VentaDetalle con folio VTD-L<id>).
  - Las ventas y devoluciones ya importadas que se cancelaron después en
    scv_web (dejan de venir en la exportación) se borran, para que no sigan
    contando en reportes y comisiones (p. ej. la remisión 0301R3144,
    cancelada al día siguiente y vuelta a hacer). Solo se buscan desde la
    primera fecha de la exportación, para no borrar historia si se exportó
    con otro --desde.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils.text import slugify

from apps.core import scv_web
from apps.core.scv_web import CUATRO, DOS, decimal, texto
from apps.ventas.models import DevolucionCliente, DevolucionClienteDetalle, Venta, VentaDetalle, VentaPago

COLUMNAS_VENTA = [
    "id", "tipo", "folio", "fecha", "id_cliente", "almacen", "estado_pago", "efectivo_recibido", "total",
    "id_vendedor",
]
COLUMNAS_PRODUCTO = [
    "id", "id_documento", "codigo", "cantidad", "costo", "precio", "importe", "total", "tipo_precio",
]
COLUMNAS_PAGO = ["id", "id_documento", "clave_sat", "importe", "referencia"]
COLUMNAS_DEVOLUCION = ["id", "folio", "fecha", "id_documento_origen", "observaciones"]
COLUMNAS_DEVOLUCION_PRODUCTO = ["id", "id_documento", "codigo", "cantidad"]

COSTO_ANOMALO_VECES = 3
LOTE = 2000
# En scv_web, Precio 6 a 10 son los precios especiales por sucursal: no salen
# en las columnas Precio 1-5 del Excel de comisiones (ver
# VentaDetalle.precio_especial).
PRIMER_PRECIO_ESPECIAL = 6


def _es_precio_especial(renglon):
    return int(renglon["tipo_precio"] or 0) >= PRIMER_PRECIO_ESPECIAL


class Command(BaseCommand):
    help = "Importa las ventas históricas de scv_web desde datos/scv_web/*.tsv (ver exportar_scv_web)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo valida y reporta.")
        parser.add_argument("--directorio", default=str(scv_web.DATA_DIR))
        parser.add_argument(
            "--solo-vendedores", action="store_true",
            help="Solo asigna el vendedor (Venta.created_by) a las ventas ya importadas; no importa nada más.",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]
        self.directorio = options["directorio"]
        if options["solo_vendedores"]:
            self._asignar_vendedores()
            return
        try:
            self._preparar()
        except (ValueError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc

        self._importar_ventas()
        self._importar_devoluciones()
        self._quitar_ventas_canceladas()
        self._reportar()

    # --- Preparación ---------------------------------------------------------

    def _preparar(self):
        self.stats = {
            "ventas": 0, "ya_importadas": 0, "renglones": 0, "pagos_divididos": 0,
            "sin_cliente": 0, "sin_renglones": 0, "renglones_sin_producto": 0, "importe_sin_producto": Decimal("0"),
            "costo_anomalo": 0, "diferencia_total": Decimal("0"), "devoluciones": 0, "devoluciones_omitidas": 0,
            "canceladas": [], "canceladas_conservadas": [], "devoluciones_canceladas": [],
        }
        self.errores = []
        with transaction.atomic():
            # En el dry-run nada de esto se guarda: Almacenes y los mapeos solo
            # cuentan lo que se crearía.
            self.almacenes = scv_web.Almacenes(crear=not self.dry_run)
            self.clientes = scv_web.ClientesLegado(scv_web.leer_asociados(self.directorio), crear=not self.dry_run)
            self.vendedores = scv_web.VendedoresLegado(self.directorio, crear=not self.dry_run)
        self.productos = scv_web.productos_por_sku()
        self.formas_pago = scv_web.formas_pago_por_clave()
        self.listas = scv_web.listas_por_tipo_precio()
        self.importadas = dict(Venta.objects.exclude(id_legado=None).values_list("id_legado", "pk"))
        self.renglones_importados = set(
            VentaDetalle.objects.filter(folio__startswith="VTD-L").values_list("folio", flat=True)
        )
        if self.formas_pago.get("99") is None:
            raise ValueError("Falta la forma de pago SAT 99 (Por definir) en el catálogo fiscal.")

    # --- Ventas --------------------------------------------------------------

    def _importar_ventas(self):
        productos = scv_web.Emparejador(scv_web.agrupar_por(
            scv_web.leer_tsv(self.directorio, "ventas_productos", COLUMNAS_PRODUCTO), "id_documento"
        ))
        pagos = scv_web.Emparejador(scv_web.agrupar_por(
            scv_web.leer_tsv(self.directorio, "ventas_pagos", COLUMNAS_PAGO), "id_documento"
        ))
        lote, faltantes, especiales = [], [], []
        exportadas, fechas = set(), []
        for fila in scv_web.leer_tsv(self.directorio, "ventas", COLUMNAS_VENTA):
            id_venta = int(fila["id"])
            exportadas.add(id_venta)
            fechas.append(fila["fecha"])
            renglones, cobros = productos.de(id_venta), pagos.de(id_venta)
            if id_venta in self.importadas:
                self.stats["ya_importadas"] += 1
                especiales.extend(f"VTD-L{r['id']}" for r in renglones if _es_precio_especial(r))
                # Renglones que se omitieron al importarla porque su producto
                # todavía no existía en sitordillo (ver
                # import_legacy_productos --solo-nuevos): se completan ahora.
                pendientes = [r for r in renglones if f"VTD-L{r['id']}" not in self.renglones_importados]
                for detalle in self._renglones(pendientes, contar=False):
                    detalle.venta_id = self.importadas[id_venta]
                    faltantes.append(detalle)
                continue
            armada = self._armar_venta(fila, renglones, cobros)
            if armada is not None:
                lote.append(armada)
            if len(lote) >= LOTE:
                self._guardar(lote)
                lote = []
        if lote:
            self._guardar(lote)
        self.stats["renglones_completados"] = len(faltantes)
        if faltantes and not self.dry_run:
            VentaDetalle.objects.bulk_create(faltantes, batch_size=5000)
        # Renglones importados antes de que se guardara el precio especial.
        self.stats["precio_especial_marcado"] = 0
        if not self.dry_run:
            for inicio in range(0, len(especiales), 5000):
                self.stats["precio_especial_marcado"] += VentaDetalle.objects.filter(
                    folio__in=especiales[inicio:inicio + 5000], precio_especial=False
                ).update(precio_especial=True)
        self.exportadas, self.fechas_exportadas = exportadas, fechas

    def _quitar_ventas_canceladas(self):
        """Borra las ventas importadas desde la primera fecha de la exportación
        que ya no vienen en ella: se cancelaron después en scv_web. Una venta histórica
        no movió inventario ni generó cuenta por cobrar, así que no deja nada
        colgando; la que tiene una devolución (u otro documento que la
        proteja) se conserva y se reporta. Va después de las devoluciones,
        para que antes se quiten las canceladas que la protegían."""
        if not self.fechas_exportadas:
            return
        desde = scv_web.fecha_hora(min(self.fechas_exportadas))
        ids = [
            id_legado for id_legado in Venta.objects.exclude(id_legado=None)
            .filter(fecha_venta__gte=desde).values_list("id_legado", flat=True)
            if id_legado not in self.exportadas
        ]
        for venta in Venta.objects.filter(id_legado__in=ids).order_by("fecha_venta"):
            if not self.dry_run:
                try:
                    with transaction.atomic():
                        venta.delete()
                except ProtectedError:
                    self.stats["canceladas_conservadas"].append(venta.folio)
                    continue
            self.stats["canceladas"].append(venta.folio)
            self.importadas.pop(venta.id_legado, None)

    def _renglones(self, renglones, contar=True):
        """Los VentaDetalle (sin venta) de los renglones de scv_web que se
        pueden importar. `contar`: si se suman a las estadísticas de lo
        omitido (no, al completar una venta ya importada)."""
        detalles = []
        for r in renglones:
            producto_id = self.productos.get(texto(r["codigo"]))
            total = decimal(r["total"])
            cantidad = decimal(r["cantidad"])
            if producto_id is None or not cantidad or cantidad <= 0:
                if contar:
                    self.stats["renglones_sin_producto"] += 1
                    self.stats["importe_sin_producto"] += total
                continue
            precio = (Decimal(r["total"]) / cantidad).quantize(DOS)
            detalle = VentaDetalle(
                folio=f"VTD-L{r['id']}", slug=f"vtd-l{r['id']}", producto_id=producto_id,
                cantidad=cantidad, precio_unitario=precio, descuento=Decimal("0.00"),
                lista_precio_id=self.listas.get(r["tipo_precio"]), costo_unitario=self._costo(r, contar),
                precio_especial=_es_precio_especial(r),
            )
            if contar:
                self.stats["diferencia_total"] += abs(detalle.subtotal - total)
            detalles.append(detalle)
        return detalles

    def _armar_venta(self, fila, renglones, cobros):
        id_venta = int(fila["id"])
        cliente_id = self.clientes.pk_de(int(fila["id_cliente"]))
        if cliente_id is None:
            self.stats["sin_cliente"] += 1
            return None
        try:
            almacen = self.almacenes.de_venta(fila["almacen"])
        except KeyError:
            self.errores.append(f"venta {fila['folio']}: almacén {fila['almacen']!r} sin equivalente")
            return None

        detalles = self._renglones(renglones)
        if not detalles:
            self.stats["sin_renglones"] += 1
            return None

        total_venta = sum((d.subtotal for d in detalles), Decimal("0.00"))
        cobros = [c for c in cobros if (decimal(c["importe"]) or 0) > 0]
        venta = Venta(
            folio=texto(fila["folio"], 20), slug=slugify(f"{fila['folio']}-{id_venta}"), id_legado=id_venta,
            cliente_id=cliente_id, almacen=almacen, fecha_venta=scv_web.fecha_hora(fila["fecha"]),
            es_remision=fila["tipo"] == "NOTA_REMISION", created_by_id=self.vendedores.pk_de(fila["id_vendedor"]),
        )
        pagos = []
        if len(cobros) == 1:
            venta.forma_pago_id = self._forma_pago(cobros[0]["clave_sat"])
            venta.referencia_pago = texto(cobros[0]["referencia"], 50)
            recibido = decimal(fila["efectivo_recibido"])
            if cobros[0]["clave_sat"] == Venta.CLAVE_EFECTIVO and recibido and recibido >= total_venta:
                venta.efectivo_recibido = recibido
        elif cobros:
            self.stats["pagos_divididos"] += 1
            pagos = [
                VentaPago(
                    folio=f"VTP-L{c['id']}", slug=f"vtp-l{c['id']}", forma_pago_id=self._forma_pago(c["clave_sat"]),
                    monto=decimal(c["importe"]), referencia=texto(c["referencia"], 50),
                )
                for c in cobros
            ]
        else:
            venta.forma_pago_id = self.formas_pago["99"]
        return venta, detalles, pagos

    def _costo(self, r, contar=True):
        costo, precio = decimal(r["costo"], CUATRO), decimal(r["precio"], CUATRO)
        if not costo or costo <= 0:
            return None
        if precio and costo > precio * COSTO_ANOMALO_VECES:
            if contar:
                self.stats["costo_anomalo"] += 1
            return None
        return costo

    def _forma_pago(self, clave):
        # Las claves de scv_web son las del SAT; la 99 (Por definir) es la de
        # sus ventas a crédito ("98 NA") y la de cualquier clave desconocida.
        return self.formas_pago.get(clave) or self.formas_pago["99"]

    def _guardar(self, lote):
        self.stats["ventas"] += len(lote)
        self.stats["renglones"] += sum(len(detalles) for _, detalles, _ in lote)
        if self.dry_run:
            return
        with transaction.atomic():
            ventas = Venta.objects.bulk_create([venta for venta, _, _ in lote])
            detalles, pagos = [], []
            for venta, (_, sus_detalles, sus_pagos) in zip(ventas, lote):
                for objeto in (*sus_detalles, *sus_pagos):
                    objeto.venta = venta
                detalles.extend(sus_detalles)
                pagos.extend(sus_pagos)
            VentaDetalle.objects.bulk_create(detalles, batch_size=5000)
            VentaPago.objects.bulk_create(pagos, batch_size=5000)
        self.importadas.update((venta.id_legado, venta.pk) for venta in ventas)
        self.stdout.write(f"  ... {self.stats['ventas']:,} ventas")

    # --- Vendedores de ventas ya importadas ----------------------------------

    def _asignar_vendedores(self):
        try:
            with transaction.atomic():
                vendedores = scv_web.VendedoresLegado(self.directorio, crear=not self.dry_run)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        accion = "Se crearían" if self.dry_run else "Se crearon"
        self.stdout.write(f"{accion} {len(vendedores.creados)} usuarios inactivos de vendedor: "
                          + ", ".join(vendedores.creados))

        por_vendedor, sin_vendedor = {}, 0
        for fila in scv_web.leer_tsv(self.directorio, "ventas", COLUMNAS_VENTA):
            pk = vendedores.pk_de(fila["id_vendedor"])
            if pk is None:
                sin_vendedor += 1
                continue
            por_vendedor.setdefault(pk, []).append(int(fila["id"]))

        actualizadas = 0
        if not self.dry_run:
            with transaction.atomic():
                for pk, ids in por_vendedor.items():
                    for inicio in range(0, len(ids), 5000):
                        actualizadas += Venta.objects.filter(
                            id_legado__in=ids[inicio:inicio + 5000], created_by=None
                        ).update(created_by_id=pk)
        else:
            actualizadas = Venta.objects.exclude(id_legado=None).filter(created_by=None).count()
        self.stdout.write(self.style.SUCCESS(
            f"Ventas con vendedor asignado: {actualizadas:,} (sin vendedor en scv_web: {sin_vendedor:,})"
        ))

    # --- Devoluciones --------------------------------------------------------

    def _importar_devoluciones(self):
        productos = scv_web.Emparejador(scv_web.agrupar_por(
            scv_web.leer_tsv(self.directorio, "devoluciones_productos", COLUMNAS_DEVOLUCION_PRODUCTO), "id_documento"
        ))
        ya = set(DevolucionCliente.objects.exclude(id_legado=None).values_list("id_legado", flat=True))
        filas = list(scv_web.leer_tsv(self.directorio, "devoluciones", COLUMNAS_DEVOLUCION))
        if filas:
            # Las ya importadas que se cancelaron después en scv_web (ver
            # _quitar_ventas_canceladas); sus renglones se borran en cascada.
            exportadas = {int(fila["id"]) for fila in filas}
            desde = min(scv_web.fecha_hora(fila["fecha"]).date() for fila in filas)
            canceladas = DevolucionCliente.objects.exclude(id_legado=None).filter(
                fecha__gte=desde
            ).exclude(id_legado__in=exportadas)
            self.stats["devoluciones_canceladas"] = list(canceladas.values_list("folio", flat=True))
            if not self.dry_run:
                canceladas.delete()
        for fila in filas:
            renglones = productos.de(int(fila["id"]))
            if int(fila["id"]) in ya:
                continue
            venta = Venta.objects.filter(id_legado=int(fila["id_documento_origen"])).first()
            if venta is None:
                # La venta original es anterior al periodo exportado (o no se
                # importó): no hay a qué ligar la devolución.
                self.stats["devoluciones_omitidas"] += 1
                continue
            disponibles = {}
            for detalle in venta.detalles.all():
                disponibles.setdefault(detalle.producto_id, []).append([detalle, detalle.cantidad])
            lineas = []
            for r in renglones:
                cantidad = decimal(r["cantidad"])
                for par in disponibles.get(self.productos.get(texto(r["codigo"])), []):
                    if cantidad and par[1] >= cantidad:
                        lineas.append(DevolucionClienteDetalle(venta_detalle=par[0], cantidad=cantidad))
                        par[1] -= cantidad
                        break
            if not lineas:
                self.stats["devoluciones_omitidas"] += 1
                continue
            self.stats["devoluciones"] += 1
            if self.dry_run:
                continue
            with transaction.atomic():
                devolucion = DevolucionCliente(
                    folio=texto(fila["folio"], 20), slug=slugify(f"{fila['folio']}-{fila['id']}"),
                    id_legado=int(fila["id"]), venta=venta, fecha=scv_web.fecha_hora(fila["fecha"]).date(),
                    motivo=texto(fila["observaciones"]),
                )
                devolucion.save()
                for linea in lineas:
                    linea.devolucion = devolucion
                    linea.save()

    # --- Reporte -------------------------------------------------------------

    def _reportar(self):
        s = self.stats
        if self.dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
        if self.almacenes.creados:
            accion = "Se crearían" if self.dry_run else "Se crearon"
            self.stdout.write(f"{accion} {len(self.almacenes.creados)} almacenes inactivos: "
                              + "; ".join(self.almacenes.creados))
        self.stdout.write(f"Clientes: {self.clientes.resultado}")
        if self.vendedores.creados:
            accion = "Se crearían" if self.dry_run else "Se crearon"
            self.stdout.write(f"{accion} {len(self.vendedores.creados)} usuarios inactivos de vendedor.")
        self.stdout.write(self.style.SUCCESS(
            f"Ventas={s['ventas']:,} renglones={s['renglones']:,} con pago dividido={s['pagos_divididos']:,} "
            f"(ya importadas antes: {s['ya_importadas']:,}; renglones que se les completaron: "
            f"{s.get('renglones_completados', 0):,}; marcados con precio especial: {s.get('precio_especial_marcado', 0):,})"
        ))
        self.stdout.write(
            f"Devoluciones={s['devoluciones']} (omitidas sin venta o renglón de origen: {s['devoluciones_omitidas']})"
        )
        accion = "Se quitarían" if self.dry_run else "Se quitaron"
        self.stdout.write(
            f"Canceladas después en scv_web: {accion} {len(s['canceladas'])} ventas "
            f"({', '.join(s['canceladas'][:20])}) y {len(s['devoluciones_canceladas'])} devoluciones "
            f"({', '.join(s['devoluciones_canceladas'][:20])})"
        )
        if s["canceladas_conservadas"]:
            self.stdout.write(self.style.WARNING(
                f"  Canceladas en scv_web pero conservadas por tener una devolución u otro documento: "
                f"{', '.join(s['canceladas_conservadas'][:20])}"
            ))
        self.stdout.write(
            f"Omitidas: sin cliente={s['sin_cliente']} sin renglones importables={s['sin_renglones']} · "
            f"renglones sin producto en sitordillo={s['renglones_sin_producto']} (${s['importe_sin_producto']:,.2f}) · "
            f"costos anómalos dejados vacíos={s['costo_anomalo']} · "
            f"diferencia por redondeo contra scv_web=${s['diferencia_total']:,.2f}"
        )
        for error in [*self.clientes.errores, *self.errores][:20]:
            self.stdout.write(self.style.WARNING(f"  - {error}"))
