"""Borra las transacciones de prueba (ventas, compras, inventario, traspasos,
cotizaciones, pedidos, cuentas por cobrar/pagar y facturas) antes de importar
el historial real de scv_web (ver import_legacy_ventas / import_legacy_compras).

Decisión del usuario (2026-10-26): hasta la importación, en sitordillo solo
son datos reales los catálogos -productos, clientes, proveedores- y los
gastos; todo lo transaccional es de prueba y se borra. No se tocan catálogos,
turnos (los gastos reales los referencian), retiros de caja, gastos ni la
configuración (bancos, empresa, recetas de conversión).

Sin --aplicar solo muestra cuánto se borraría. Se niega a correr si ya hay
ventas o compras importadas del sistema anterior: a partir de ahí lo
transaccional ya no es de prueba.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Del que depende de otros al que no: cada modelo se borra completo, en este
# orden, para que ninguna referencia PROTECT lo impida.
ORDEN_DE_BORRADO = [
    "facturacion.Factura",
    "cobros.Cobro",
    "cobros.CuentaPorCobrar",
    "pagos.Pago",
    "pagos.ReciboPago",
    "pagos.CuentaPorPagar",
    "ventas.DevolucionClienteDetalle",
    "ventas.DevolucionCliente",
    "cotizaciones.CotizacionDetalle",
    "cotizaciones.Cotizacion",
    "pedidos.PedidoDetalleLote",
    "pedidos.PedidoDetalle",
    "pedidos.Pedido",
    "ventas.VentaDetalleLote",
    "ventas.VentaPago",
    "ventas.VentaDetalle",
    "ventas.Venta",
    "facturacion.FacturaGlobal",
    "traspasos.TraspasoLote",
    "traspasos.TraspasoDetalle",
    "traspasos.Traspaso",
    "inventario.MovimientoAlmacenLote",
    "inventario.MovimientoAlmacenDetalle",
    "inventario.MovimientoAlmacen",
    "inventario.Conversion",
    "inventario.EnsamblePaquete",
    "inventario.MovimientoInventario",
    "inventario.Lote",
    "compras.OrdenCompraDetalle",
    "compras.OrdenCompra",
]


class Command(BaseCommand):
    help = "Borra las transacciones de prueba antes de importar el historial de scv_web."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Borra de verdad (sin esto solo cuenta).")

    def handle(self, *args, **options):
        Venta = apps.get_model("ventas", "Venta")
        OrdenCompra = apps.get_model("compras", "OrdenCompra")
        if Venta.objects.exclude(id_legado=None).exists() or OrdenCompra.objects.exclude(id_legado=None).exists():
            raise CommandError(
                "Ya hay ventas o compras importadas del sistema anterior: lo transaccional ya no es de prueba "
                "y este comando no se puede usar."
            )

        modelos = [apps.get_model(etiqueta) for etiqueta in ORDEN_DE_BORRADO]
        for modelo in modelos:
            self.stdout.write(f"  {modelo._meta.label}: {modelo.objects.count():,}")
        if not options["aplicar"]:
            self.stdout.write(self.style.WARNING("Sin --aplicar: no se borró nada."))
            return

        with transaction.atomic():
            MovimientoAlmacen = apps.get_model("inventario", "MovimientoAlmacen")
            # Un movimiento puede apuntar a otro (PROTECT): primero los que apuntan.
            MovimientoAlmacen.objects.exclude(movimiento_relacionado=None).delete()
            for modelo in modelos:
                modelo.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Transacciones de prueba borradas."))
