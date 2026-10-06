from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.fiscal.models import FormaPago
from apps.inventario.models import Lote, MovimientoInventario
from apps.products.models import Almacen, Producto, PuntoVenta, Turno
from apps.ventas.models import Venta, VentaDetalleLote

from apps.pedidos.models import Pedido, PedidoDetalleLote

User = get_user_model()


class PedidoFlujoTests(TestCase):
    """Flujo completo: mostrador levanta el pedido (aparta inventario),
    lo edita o lo cancela (libera), y caja lo convierte en venta (sale de
    los mismos lotes apartados)."""

    @classmethod
    def setUpTestData(cls):
        cls.almacen = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.otra_sucursal = Almacen.objects.create(nombre="Sucursal Norte", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        cls.caja = PuntoVenta.objects.create(almacen=cls.almacen, codigo="C1", numero=1, nombre="Caja 1")
        cls.mostrador_pv = PuntoVenta.objects.create(
            almacen=cls.almacen, codigo="M1", numero=2, nombre="Mostrador 1", tipo=PuntoVenta.Tipo.PEDIDO,
        )
        cls.caja_norte = PuntoVenta.objects.create(almacen=cls.otra_sucursal, codigo="C1", numero=1, nombre="Caja Norte")
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.producto = Producto.objects.create(nombre="Croqueta 20kg", sku="CRQ20", precio_venta=Decimal("500.00"))
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]

        cls.mostrador = User.objects.create_user(username="mostrador", password="S3guridad!2026")
        cls.mostrador.groups.add(Group.objects.get(name="Mostrador y Cotización"))
        cls.cajero = User.objects.create_user(username="cajero", password="S3guridad!2026")
        cls.cajero.groups.add(Group.objects.get(name="Ventas y Caja"))

    def setUp(self):
        self.lote_viejo = self._lote(Decimal("3"), date(2026, 1, 1), Decimal("300.00"))
        self.lote_nuevo = self._lote(Decimal("10"), date(2026, 6, 1), Decimal("320.00"))
        self.turno_mostrador = Turno.objects.create(punto_venta=self.mostrador_pv, usuario=self.mostrador)

    def _lote(self, cantidad, fecha_ingreso, costo):
        return Lote.objects.create(
            producto=self.producto, almacen=self.almacen, fecha_ingreso=fecha_ingreso,
            costo_unitario=costo, cantidad_inicial=cantidad, cantidad_disponible=cantidad,
        )

    def _existencia(self):
        return sum(l.cantidad_disponible for l in Lote.objects.filter(producto=self.producto, almacen=self.almacen))

    def _post_pedido(self, url, cantidad, filas_existentes=None):
        datos = {
            "cliente": self.cliente.pk,
            "observaciones": "Pasa mañana",
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-producto": self.producto.pk,
            "detalles-0-cantidad": str(cantidad),
            "detalles-0-precio_unitario": "1.00",
        }
        if filas_existentes:
            datos["detalles-INITIAL_FORMS"] = "1"
            datos["detalles-0-id"] = filas_existentes[0].pk
        return self.client.post(url, datos)

    def _levantar_pedido(self, cantidad):
        self.client.force_login(self.mostrador)
        respuesta = self._post_pedido(reverse("pedidos:pedido-create"), cantidad)
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, "context", None) and respuesta.context["form"].errors)
        return Pedido.objects.latest("id")

    def test_levantar_pedido_aparta_inventario_fifo(self):
        pedido = self._levantar_pedido(5)

        self.assertEqual(pedido.estatus, Pedido.Estatus.ABIERTO)
        self.assertEqual(pedido.almacen, self.almacen)
        self.assertEqual(pedido.numero_documento, "0102P0000001")
        self.assertEqual(pedido.detalles.get().precio_unitario, Decimal("500.00"))
        self.assertEqual(self._existencia(), Decimal("8"))
        apartados = {a.lote_id: a.cantidad for a in PedidoDetalleLote.objects.filter(detalle__pedido=pedido)}
        self.assertEqual(apartados, {self.lote_viejo.pk: Decimal("3"), self.lote_nuevo.pk: Decimal("2")})
        self.assertEqual(
            MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.PEDIDO, cantidad__lt=0).count(), 2,
        )

    def test_sin_existencia_no_se_guarda_nada(self):
        self.client.force_login(self.mostrador)
        respuesta = self._post_pedido(reverse("pedidos:pedido-create"), 20)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertFalse(Pedido.objects.exists())
        self.assertEqual(self._existencia(), Decimal("13"))
        self.mostrador_pv.refresh_from_db()
        self.assertEqual(self.mostrador_pv.consecutivo_pedido, 0)

    def test_sin_turno_no_puede_levantar_pedido(self):
        self.turno_mostrador.cerrar()
        self.client.force_login(self.mostrador)
        respuesta = self.client.get(reverse("pedidos:pedido-create"))
        self.assertRedirects(respuesta, reverse("products:turno-list"), fetch_redirect_response=False)

    def test_editar_pedido_reaparta_con_la_nueva_cantidad(self):
        pedido = self._levantar_pedido(5)
        respuesta = self._post_pedido(
            reverse("pedidos:pedido-update", args=[pedido.pk]), 12, filas_existentes=list(pedido.detalles.all()),
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._existencia(), Decimal("1"))
        total_apartado = sum(a.cantidad for a in PedidoDetalleLote.objects.filter(detalle__pedido=pedido))
        self.assertEqual(total_apartado, Decimal("12"))

    def test_editar_sin_existencia_deja_el_apartado_original(self):
        pedido = self._levantar_pedido(5)
        respuesta = self._post_pedido(
            reverse("pedidos:pedido-update", args=[pedido.pk]), 14, filas_existentes=list(pedido.detalles.all()),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._existencia(), Decimal("8"))
        self.assertEqual(pedido.detalles.get().cantidad, Decimal("5"))

    def test_cancelar_regresa_la_mercancia_a_los_mismos_lotes(self):
        pedido = self._levantar_pedido(5)
        respuesta = self.client.post(reverse("pedidos:pedido-cancelar", args=[pedido.pk]), {"motivo": "No vino"})

        self.assertEqual(respuesta.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estatus, Pedido.Estatus.CANCELADO)
        self.assertEqual(pedido.motivo_cancelacion, "No vino")
        self.lote_viejo.refresh_from_db()
        self.lote_nuevo.refresh_from_db()
        self.assertEqual(self.lote_viejo.cantidad_disponible, Decimal("3"))
        self.assertEqual(self.lote_nuevo.cantidad_disponible, Decimal("10"))
        self.assertFalse(PedidoDetalleLote.objects.filter(detalle__pedido=pedido).exists())

    def test_mostrador_no_puede_convertir_a_venta(self):
        pedido = self._levantar_pedido(5)
        respuesta = self.client.get(reverse("pedidos:pedido-convertir", args=[pedido.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def _abrir_turno_cajero(self, punto_venta):
        # Mostrador sigue con su turno abierto en su propio punto de venta:
        # caja abre el suyo en la caja sin estorbarse.
        return Turno.objects.create(punto_venta=punto_venta, usuario=self.cajero)

    def test_caja_convierte_el_pedido_desde_los_lotes_apartados(self):
        pedido = self._levantar_pedido(5)
        self._abrir_turno_cajero(self.caja)
        self.client.force_login(self.cajero)

        respuesta = self.client.post(
            reverse("pedidos:pedido-convertir", args=[pedido.pk]),
            {"cliente": self.cliente.pk, "forma_pago": self.efectivo.pk, "observaciones": ""},
        )

        self.assertRedirects(respuesta, reverse("ventas:venta-list"), fetch_redirect_response=False)
        pedido.refresh_from_db()
        venta = Venta.objects.get()
        self.assertEqual(pedido.estatus, Pedido.Estatus.CONVERTIDO)
        self.assertEqual(pedido.venta, venta)
        self.assertEqual(venta.total, Decimal("2500.00"))
        self.assertEqual(venta.vendedor_mostrador, self.mostrador)
        # La existencia no se vuelve a descontar: ya había salido al apartar.
        self.assertEqual(self._existencia(), Decimal("8"))
        lotes_venta = {l.lote_id: (l.cantidad, l.costo_unitario) for l in VentaDetalleLote.objects.all()}
        self.assertEqual(lotes_venta, {
            self.lote_viejo.pk: (Decimal("3"), Decimal("300.00")),
            self.lote_nuevo.pk: (Decimal("2"), Decimal("320.00")),
        })
        self.assertEqual(
            MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.SALIDA).count(), 2,
        )

        # Un segundo intento ya no hace nada.
        respuesta = self.client.post(
            reverse("pedidos:pedido-convertir", args=[pedido.pk]),
            {"cliente": self.cliente.pk, "forma_pago": self.efectivo.pk},
        )
        self.assertTemplateUsed(respuesta, "pedidos/ya_cerrado.html")
        self.assertEqual(Venta.objects.count(), 1)

    def test_no_se_convierte_con_efectivo_menor_al_total(self):
        # B19 (docs/AUDITORIA.md): la conversión no revisaba el efectivo.
        pedido = self._levantar_pedido(5)
        self._abrir_turno_cajero(self.caja)
        self.client.force_login(self.cajero)

        respuesta = self.client.post(
            reverse("pedidos:pedido-convertir", args=[pedido.pk]),
            {"cliente": self.cliente.pk, "forma_pago": self.efectivo.pk, "efectivo_recibido": "2000.00"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no puede ser menor que el total", str(respuesta.context["form"].non_field_errors()))
        self.assertFalse(Venta.objects.exists())
        pedido.refresh_from_db()
        self.assertEqual(pedido.estatus, Pedido.Estatus.ABIERTO)
        self.assertEqual(sum(a.cantidad for a in PedidoDetalleLote.objects.filter(detalle__pedido=pedido)), 5)

    def test_no_se_convierte_desde_otra_sucursal(self):
        pedido = self._levantar_pedido(5)
        self._abrir_turno_cajero(self.caja_norte)
        self.client.force_login(self.cajero)

        respuesta = self.client.post(
            reverse("pedidos:pedido-convertir", args=[pedido.pk]),
            {"cliente": self.cliente.pk, "forma_pago": self.efectivo.pk},
        )

        self.assertRedirects(respuesta, reverse("pedidos:pedido-list"), fetch_redirect_response=False)
        self.assertFalse(Venta.objects.exists())

    def test_pantallas_cargan(self):
        pedido = self._levantar_pedido(5)
        for nombre in ("pedidos:pedido-list", "pedidos:pedido-create"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        for nombre in ("pedidos:pedido-update", "pedidos:pedido-cancelar"):
            self.assertEqual(self.client.get(reverse(nombre, args=[pedido.pk])).status_code, 200, nombre)

        self._abrir_turno_cajero(self.caja)
        self.client.force_login(self.cajero)
        self.assertEqual(self.client.get(reverse("pedidos:pedido-buscar")).status_code, 200)
        respuesta = self.client.get(reverse("pedidos:pedido-buscar"), {"folio": pedido.numero_documento})
        self.assertRedirects(
            respuesta, reverse("pedidos:pedido-convertir", args=[pedido.pk]), fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(reverse("pedidos:pedido-convertir", args=[pedido.pk])), "Confirmar venta")


class TurnoPorRolTests(TestCase):
    """El rol (grupo asignado en la administración de usuarios) decide en
    qué tipo de punto de venta se puede abrir turno, y el turno de
    mostrador solo sirve para cotizar y levantar pedidos, nunca para
    cobrar."""

    @classmethod
    def setUpTestData(cls):
        cls.almacen = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.caja = PuntoVenta.objects.create(almacen=cls.almacen, codigo="C1", numero=1, nombre="Caja 1")
        cls.mostrador_pv = PuntoVenta.objects.create(
            almacen=cls.almacen, codigo="M1", numero=2, nombre="Mostrador 1", tipo=PuntoVenta.Tipo.PEDIDO,
        )
        cls.mostrador = User.objects.create_user(username="mostrador", password="S3guridad!2026")
        cls.mostrador.groups.add(Group.objects.get(name="Mostrador y Cotización"))
        cls.cajero = User.objects.create_user(username="cajero", password="S3guridad!2026")
        cls.cajero.groups.add(Group.objects.get(name="Ventas y Caja"))

    def test_mostrador_solo_ve_y_abre_turno_de_mostrador(self):
        self.client.force_login(self.mostrador)
        respuesta = self.client.get(reverse("products:turno-list"))
        self.assertEqual(list(respuesta.context["puntos_venta"]), [self.mostrador_pv])

        self.client.post(reverse("products:turno-abrir"), {"punto_venta": self.caja.pk})
        self.assertFalse(Turno.objects.filter(punto_venta=self.caja).exists())

        self.client.post(reverse("products:turno-abrir"), {"punto_venta": self.mostrador_pv.pk})
        self.assertTrue(Turno.objects.filter(punto_venta=self.mostrador_pv, usuario=self.mostrador).exists())

    def test_cajero_solo_abre_turno_de_caja(self):
        self.client.force_login(self.cajero)
        respuesta = self.client.get(reverse("products:turno-list"))
        self.assertEqual(list(respuesta.context["puntos_venta"]), [self.caja])

    def test_turno_de_mostrador_cotiza_y_levanta_pedidos(self):
        Turno.objects.create(punto_venta=self.mostrador_pv, usuario=self.mostrador)
        self.client.force_login(self.mostrador)
        self.assertEqual(self.client.get(reverse("cotizaciones:cotizacion-create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("pedidos:pedido-create")).status_code, 200)

    def test_turno_de_mostrador_no_cobra(self):
        # Aun con permiso de ventas, un turno de mostrador no sirve para cobrar.
        self.cajero.groups.add(Group.objects.get(name="Mostrador y Cotización"))
        Turno.objects.create(punto_venta=self.mostrador_pv, usuario=self.cajero)
        self.client.force_login(self.cajero)
        respuesta = self.client.get(reverse("ventas:venta-create"))
        self.assertRedirects(respuesta, reverse("products:turno-list"), fetch_redirect_response=False)
