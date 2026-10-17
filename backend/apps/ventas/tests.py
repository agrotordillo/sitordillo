import base64
import hashlib
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.fiscal.models import FormaPago
from apps.inventario.models import Lote, MovimientoInventario
from apps.products.models import Almacen, PaqueteComponente, Producto, PuntoVenta, Turno
from apps.ventas.models import (
    DevolucionCliente,
    DevolucionClienteDetalle,
    RetiroEfectivo,
    Venta,
    VentaDetalle,
    VentaDetalleLote,
    VentaPago,
)
from apps.ventas.services import registrar_devolucion, resumen_turno, validar_efectivo_recibido
from apps.ventas.ticket import construir_ticket_retiro
from apps.ventas.views import qz_views

User = get_user_model()


class DevolucionClienteTests(TestCase):
    """B06 (docs/AUDITORIA.md): la devolución tronaba con un costo promedio
    no exacto y reconstruía lo devuelto con la receta actual del paquete en
    vez de con lo que de verdad salió en la venta."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]

    def _lote(self, producto, cantidad, costo, **extra):
        return Lote.objects.create(
            producto=producto, almacen=self.sucursal, fecha_ingreso=extra.pop("fecha_ingreso", date(2026, 1, 1)),
            costo_unitario=costo, cantidad_inicial=cantidad, cantidad_disponible=cantidad, **extra,
        )

    def _venta(self, producto, cantidad, salidas):
        """`salidas`: [(lote, cantidad)] tal como las habría registrado procesar_lineas_venta."""
        venta = Venta.objects.create(cliente=self.cliente, almacen=self.sucursal, forma_pago=self.efectivo)
        detalle = VentaDetalle.objects.create(
            venta=venta, producto=producto, cantidad=cantidad, precio_unitario=Decimal("50.00"),
        )
        for lote, tomado in salidas:
            VentaDetalleLote.objects.create(detalle=detalle, lote=lote, cantidad=tomado, costo_unitario=lote.costo_unitario)
        return venta, detalle

    def _devolver(self, venta, detalle, cantidad, reingresa=True):
        devolucion = DevolucionCliente.objects.create(venta=venta, fecha=date(2026, 3, 1))
        DevolucionClienteDetalle.objects.create(
            devolucion=devolucion, venta_detalle=detalle, cantidad=cantidad, reingresa_a_inventario=reingresa,
        )
        registrar_devolucion(devolucion)
        return devolucion

    def _reingresos(self, devolucion):
        return list(
            Lote.objects.filter(movimientos__motivo__startswith=f"Devolución {devolucion.folio}").order_by("producto__sku")
        )

    def test_costo_promedio_no_exacto_se_redondea(self):
        croqueta = Producto.objects.create(nombre="Croqueta", sku="CRQ")
        viejo = self._lote(croqueta, Decimal("1"), Decimal("10.00"), numero_lote="A", fecha_caducidad=date(2027, 1, 1))
        nuevo = self._lote(croqueta, Decimal("2"), Decimal("11.00"), numero_lote="B", fecha_caducidad=date(2026, 12, 1))
        venta, detalle = self._venta(croqueta, 3, [(viejo, 1), (nuevo, 2)])

        [lote] = self._reingresos(self._devolver(venta, detalle, Decimal("1")))

        self.assertEqual(lote.costo_unitario, Decimal("10.67"))
        self.assertEqual(lote.cantidad_disponible, Decimal("1"))
        self.assertEqual(lote.almacen, self.sucursal)
        # Salió de dos números de lote: no se sabe de cuál regresa. La
        # caducidad es la más próxima de los lotes de origen.
        self.assertEqual(lote.numero_lote, "")
        self.assertEqual(lote.fecha_caducidad, date(2026, 12, 1))

    def test_devoluciones_parciales_suman_exacto_lo_que_salio(self):
        bolsa = Producto.objects.create(nombre="Bolsa", sku="BOL")
        lata = Producto.objects.create(nombre="Lata", sku="LAT")
        paquete = Producto.objects.create(
            nombre="Combo", sku="CMB", tipo=Producto.TipoProducto.PAQUETE, almacen=self.sucursal,
        )
        # 3 paquetes vendidos "virtuales": salieron 1 bolsa y 3 latas por paquete.
        lote_bolsa = self._lote(bolsa, Decimal("3"), Decimal("5.00"))
        lote_lata = self._lote(lata, Decimal("9"), Decimal("2.00"))
        venta, detalle = self._venta(paquete, 3, [(lote_bolsa, 3), (lote_lata, 9)])

        for _ in range(3):
            self._devolver(venta, detalle, Decimal("1"))

        regresado = {
            sku: sum(
                (m.cantidad for m in MovimientoInventario.objects.filter(
                    tipo=MovimientoInventario.Tipo.DEVOLUCION, lote__producto__sku=sku)),
                Decimal("0"),
            )
            for sku in ("BOL", "LAT")
        }
        self.assertEqual(regresado, {"BOL": Decimal("3"), "LAT": Decimal("9")})

    def test_regresa_lo_que_salio_aunque_el_paquete_cambie_de_receta_o_tenga_existencia_armada(self):
        bolsa = Producto.objects.create(nombre="Bolsa", sku="BOL")
        otro = Producto.objects.create(nombre="Otro componente", sku="OTR")
        paquete = Producto.objects.create(
            nombre="Combo", sku="CMB", tipo=Producto.TipoProducto.PAQUETE, almacen=self.sucursal,
        )
        lote_bolsa = self._lote(bolsa, Decimal("2"), Decimal("5.00"))
        venta, detalle = self._venta(paquete, 2, [(lote_bolsa, 2)])
        # Después de la venta: cambia la receta y además hay paquetes armados.
        PaqueteComponente.objects.create(paquete=paquete, producto_componente=otro, cantidad=1)
        self._lote(paquete, Decimal("5"), Decimal("20.00"))

        lotes = self._reingresos(self._devolver(venta, detalle, Decimal("2")))

        self.assertEqual([(l.producto, l.cantidad_inicial, l.costo_unitario) for l in lotes], [(bolsa, 2, Decimal("5.00"))])

    def test_venta_sin_registro_de_lotes_usa_el_costo_de_catalogo(self):
        producto = Producto.objects.create(nombre="Vacuna", sku="VAC", precio_costo=Decimal("33.3333"))
        venta, detalle = self._venta(producto, 2, [])

        [lote] = self._reingresos(self._devolver(venta, detalle, Decimal("1")))

        self.assertEqual((lote.producto, lote.cantidad_inicial, lote.costo_unitario), (producto, 1, Decimal("33.33")))

    def test_sin_reingreso_no_mueve_inventario(self):
        producto = Producto.objects.create(nombre="Vacuna", sku="VAC")
        lote = self._lote(producto, Decimal("1"), Decimal("10.00"))
        venta, detalle = self._venta(producto, 1, [(lote, 1)])

        devolucion = self._devolver(venta, detalle, Decimal("1"), reingresa=False)

        self.assertEqual(self._reingresos(devolucion), [])

    def test_la_vista_muestra_el_error_y_no_deja_nada_a_medias(self):
        admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        producto = Producto.objects.create(nombre="Vacuna", sku="VAC")
        lote = self._lote(producto, Decimal("1"), Decimal("10.00"))
        venta, detalle = self._venta(producto, 1, [(lote, 1)])
        self.client.force_login(admin)

        with mock.patch(
            "apps.ventas.views.devolucion_views.registrar_devolucion",
            side_effect=ValidationError("No se pudo reingresar."),
        ):
            respuesta = self.client.post(reverse("ventas:venta-devolver", args=[venta.pk]), {
                "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
                "form-0-venta_detalle_id": detalle.pk, "form-0-cantidad": "1",
                "form-0-reingresa_a_inventario": "on",
            })

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("No se pudo reingresar.", [str(m) for m in respuesta.context["messages"]])
        self.assertFalse(DevolucionCliente.objects.exists())


class FirmaQZTrayTests(TestCase):
    """B32 (docs/AUDITORIA.md): la llave privada del servidor firmaba
    cualquier texto para cualquier usuario con sesión."""

    @classmethod
    def setUpTestData(cls):
        cls.cajero = User.objects.create_user(username="cajero", password="S3guridad!2026")
        cls.cajero.user_permissions.add(Permission.objects.get(codename="view_venta"))
        cls.sin_permiso = User.objects.create_user(username="otro", password="S3guridad!2026")

    def setUp(self):
        self.llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ruta = Path(carpeta, "qz-private-key.pem")
        ruta.write_bytes(self.llave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ))
        parche = mock.patch.object(qz_views, "_PRIVATE_KEY_PATH", ruta)
        parche.start()
        self.addCleanup(parche.stop)
        self.url = reverse("ventas:qz-firmar")

    def test_solo_firma_hashes_de_qz_tray_para_quien_imprime_tickets(self):
        solicitud = hashlib.sha256(b'{"call":"print"}').hexdigest()

        self.client.force_login(self.sin_permiso)
        self.assertEqual(self.client.get(self.url, {"request": solicitud}).status_code, 403)

        self.client.force_login(self.cajero)
        self.assertEqual(self.client.get(self.url, {"request": "cualquier texto"}).status_code, 400)
        respuesta = self.client.get(self.url, {"request": solicitud})
        self.assertEqual(respuesta.status_code, 200)
        self.llave.public_key().verify(
            base64.b64decode(respuesta.content), solicitud.encode(), padding.PKCS1v15(), hashes.SHA512(),
        )


class CobroTests(TestCase):
    """B19 y B24 (docs/AUDITORIA.md): las conversiones aceptaban un efectivo
    recibido menor al total, y el cobro dividido conservaba el "recibido"
    oculto de cuando se eligió Efectivo."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.caja = PuntoVenta.objects.create(almacen=cls.sucursal, codigo="C1", numero=1, nombre="Caja 1")
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.tarjeta = FormaPago.objects.get_or_create(clave="04", defaults={"descripcion": "Tarjeta de crédito"})[0]
        cls.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_venta=Decimal("100.00"))
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

    def setUp(self):
        Lote.objects.create(
            producto=self.producto, almacen=self.sucursal, fecha_ingreso=date(2026, 1, 1),
            costo_unitario=Decimal("60.00"), cantidad_inicial=5, cantidad_disponible=5,
        )
        Turno.objects.create(punto_venta=self.caja, usuario=self.admin)
        self.client.force_login(self.admin)

    def test_validar_efectivo_recibido(self):
        venta = Venta.objects.create(cliente=self.cliente, almacen=self.sucursal, forma_pago=self.efectivo)
        VentaDetalle.objects.create(venta=venta, producto=self.producto, cantidad=1, precio_unitario=Decimal("100.00"))

        for recibido in (None, Decimal("100.00"), Decimal("500.00")):
            venta.efectivo_recibido = recibido
            validar_efectivo_recibido(venta)
        venta.efectivo_recibido = Decimal("99.99")
        with self.assertRaisesMessage(ValueError, "no puede ser menor que el total"):
            validar_efectivo_recibido(venta)

    def test_el_cobro_dividido_descarta_el_efectivo_recibido(self):
        respuesta = self.client.post(reverse("ventas:venta-create"), {
            "cliente": self.cliente.pk, "forma_pago": self.efectivo.pk, "efectivo_recibido": "1000.00",
            "pago_dividido": "on", "observaciones": "",
            "detalles-TOTAL_FORMS": 1, "detalles-INITIAL_FORMS": 0, "detalles-MIN_NUM_FORMS": 0,
            "detalles-MAX_NUM_FORMS": 1000,
            "detalles-0-producto": self.producto.pk, "detalles-0-cantidad": "1", "detalles-0-precio_unitario": "100.00",
            "pagos-TOTAL_FORMS": 2, "pagos-INITIAL_FORMS": 0, "pagos-MIN_NUM_FORMS": 0, "pagos-MAX_NUM_FORMS": 1000,
            "pagos-0-forma_pago": self.efectivo.pk, "pagos-0-monto": "60.00", "pagos-0-recibido": "100.00",
            "pagos-1-forma_pago": self.tarjeta.pk, "pagos-1-monto": "40.00",
        })

        venta = Venta.objects.get()
        self.assertRedirects(respuesta, reverse("ventas:venta-ticket", args=[venta.pk]), fetch_redirect_response=False)
        self.assertIsNone(venta.forma_pago)
        self.assertIsNone(venta.efectivo_recibido)
        self.assertIsNone(venta.cambio)


class ReporteVentasPorCobroTests(TestCase):
    """Filtro por forma de cobro del listado de ventas y su PDF: el total
    de una forma de cobro cuenta solo la parte cobrada así en una venta de
    cobro dividido, no el total de la venta."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.tarjeta = FormaPago.objects.get_or_create(clave="04", defaults={"descripcion": "Tarjeta de crédito"})[0]
        cls.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_venta=Decimal("100.00"))
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

        def venta(precio, forma_pago=None, pagos=()):
            v = Venta.objects.create(cliente=cls.cliente, almacen=cls.sucursal, forma_pago=forma_pago)
            VentaDetalle.objects.create(venta=v, producto=cls.producto, cantidad=1, precio_unitario=precio)
            for fp, monto in pagos:
                VentaPago.objects.create(venta=v, forma_pago=fp, monto=monto)
            return v

        cls.solo_efectivo = venta(Decimal("100.00"), cls.efectivo)
        cls.solo_tarjeta = venta(Decimal("250.00"), cls.tarjeta)
        cls.dividida = venta(Decimal("300.00"), pagos=[(cls.efectivo, Decimal("120.00")), (cls.tarjeta, Decimal("180.00"))])

    def setUp(self):
        self.client.force_login(self.admin)

    def test_filtrar_por_efectivo_suma_solo_lo_cobrado_en_efectivo(self):
        respuesta = self.client.get(reverse("ventas:venta-list"), {"forma_pago": self.efectivo.pk})

        self.assertEqual(
            {v.pk for v in respuesta.context["ventas"]}, {self.solo_efectivo.pk, self.dividida.pk}
        )
        self.assertEqual(respuesta.context["total_cobro"], Decimal("220.00"))

    def test_sin_filtro_resume_cada_forma_de_cobro(self):
        respuesta = self.client.get(reverse("ventas:venta-list"))

        resumen = {r["forma_pago"].clave: (r["monto"], r["ventas"]) for r in respuesta.context["resumen_cobro"]}
        self.assertEqual(resumen, {"01": (Decimal("220.00"), 2), "04": (Decimal("430.00"), 2)})
        self.assertEqual(respuesta.context["total_cobro"], Decimal("650.00"))

    def test_pdf_del_listado_filtrado(self):
        respuesta = self.client.get(reverse("ventas:venta-reporte-pdf"), {"forma_pago": self.tarjeta.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertTrue(respuesta.content.startswith(b"%PDF"))

    def test_forma_de_cobro_invalida_no_rompe_la_pantalla(self):
        respuesta = self.client.get(reverse("ventas:venta-list"), {"forma_pago": "abc"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["forma_pago_filtro"])


class RetiroEfectivoTests(TestCase):
    """Retiro de efectivo de la caja (por gasto o a caja fuerte): lo hace
    el cajero sobre su propio turno abierto, imprime comprobante y se
    resta del efectivo esperado en el corte."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.caja = PuntoVenta.objects.create(almacen=cls.sucursal, codigo="C1", numero=1, nombre="Caja 1")
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.tarjeta = FormaPago.objects.get_or_create(clave="04", defaults={"descripcion": "Tarjeta de crédito"})[0]
        cls.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_venta=Decimal("100.00"))
        cls.cajero = User.objects.create_user(username="cajero", password="S3guridad!2026")
        cls.cajero.user_permissions.add(*Permission.objects.filter(
            codename__in=["add_retiroefectivo", "view_retiroefectivo", "view_venta", "view_turno"]
        ))

    def setUp(self):
        self.turno = Turno.objects.create(punto_venta=self.caja, usuario=self.cajero)
        self.client.force_login(self.cajero)

    def _retirar(self, **datos):
        return self.client.post(reverse("ventas:retiro-create"), {
            "tipo": RetiroEfectivo.Tipo.GASTO, "monto": "50.00", "descripcion": "Garrafones de agua",
            "entregado_a": "", **datos,
        })

    def test_el_cajero_retira_de_su_turno_e_imprime_comprobante(self):
        respuesta = self._retirar()

        retiro = RetiroEfectivo.objects.get()
        self.assertRedirects(respuesta, reverse("ventas:retiro-ticket", args=[retiro.pk]), fetch_redirect_response=False)
        self.assertEqual(retiro.turno, self.turno)
        self.assertEqual(retiro.monto, Decimal("50.00"))

        ticket = self.client.get(reverse("ventas:retiro-ticket", args=[retiro.pk]))
        self.assertContains(ticket, "RETIRO DE EFECTIVO")
        retiro.refresh_from_db()
        self.assertEqual(retiro.veces_impreso, 1)

    def test_sin_turno_abierto_no_puede_retirar(self):
        self.turno.cerrar()

        respuesta = self._retirar()

        self.assertRedirects(respuesta, reverse("products:turno-list"), fetch_redirect_response=False)
        self.assertFalse(RetiroEfectivo.objects.exists())

    def test_monto_cero_no_se_registra(self):
        respuesta = self._retirar(monto="0")

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(RetiroEfectivo.objects.exists())

    def test_no_se_retira_de_un_turno_cerrado(self):
        self.turno.cerrar()
        retiro = RetiroEfectivo(turno=self.turno, tipo=RetiroEfectivo.Tipo.CAJA_FUERTE, monto=1, descripcion="x")

        with self.assertRaisesMessage(ValidationError, "turno ya está cerrado"):
            retiro.full_clean()

    def test_sin_permiso_no_entra(self):
        otro = User.objects.create_user(username="mostrador", password="S3guridad!2026")
        self.client.force_login(otro)

        self.assertEqual(self.client.get(reverse("ventas:retiro-create")).status_code, 403)

    def test_el_corte_resta_los_retiros_del_efectivo_cobrado(self):
        efectivo = Venta.objects.create(
            cliente=self.cliente, almacen=self.sucursal, forma_pago=self.efectivo, turno=self.turno
        )
        VentaDetalle.objects.create(venta=efectivo, producto=self.producto, cantidad=1, precio_unitario=Decimal("100.00"))
        dividida = Venta.objects.create(cliente=self.cliente, almacen=self.sucursal, turno=self.turno)
        VentaDetalle.objects.create(venta=dividida, producto=self.producto, cantidad=1, precio_unitario=Decimal("300.00"))
        VentaPago.objects.create(venta=dividida, forma_pago=self.efectivo, monto=Decimal("120.00"))
        VentaPago.objects.create(venta=dividida, forma_pago=self.tarjeta, monto=Decimal("180.00"))
        RetiroEfectivo.objects.create(turno=self.turno, tipo=RetiroEfectivo.Tipo.GASTO, monto=50, descripcion="Agua")
        RetiroEfectivo.objects.create(
            turno=self.turno, tipo=RetiroEfectivo.Tipo.CAJA_FUERTE, monto=100, descripcion="Caja fuerte"
        )

        resumen = resumen_turno(self.turno)

        self.assertEqual(resumen["efectivo_cobrado"], Decimal("220.00"))
        self.assertEqual(resumen["total_retiros"], Decimal("150.00"))
        self.assertEqual(resumen["efectivo_esperado"], Decimal("70.00"))
        self.assertEqual(resumen["retiros_por_tipo"], {"Gasto": Decimal("50.00"), "Envío a caja fuerte": Decimal("100.00")})
        corte = self.client.get(reverse("products:turno-corte", args=[self.turno.pk]))
        self.assertContains(corte, "Efectivo esperado")

    def test_ticket_esc_pos_del_retiro(self):
        retiro = RetiroEfectivo.objects.create(
            turno=self.turno, tipo=RetiroEfectivo.Tipo.CAJA_FUERTE, monto=Decimal("1500.00"),
            descripcion="Envío a caja fuerte", entregado_a="Gerente",
        )

        datos = construir_ticket_retiro(retiro)

        self.assertIn(b"RETIRO DE EFECTIVO", datos)
        self.assertIn(b"$1,500.00", datos)
        self.assertIn(b"Entregado a: Gerente", datos)

    def test_listado_del_dia(self):
        RetiroEfectivo.objects.create(turno=self.turno, tipo=RetiroEfectivo.Tipo.GASTO, monto=50, descripcion="Agua")

        respuesta = self.client.get(reverse("ventas:retiro-list"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["total_retiros"], Decimal("50.00"))
