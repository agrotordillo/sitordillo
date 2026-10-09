import shutil
import tempfile
import threading
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, transaction
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.compras.models import OrdenCompra
from apps.core.archivos import RutaAleatoria
from apps.core.models import EnvioUnico
from apps.core.navegacion import url_de_regreso
from apps.core.parametros import fecha as leer_fecha, filtrar_por_id, id_valido, ids_validos
from apps.cotizaciones.models import Cotizacion, CotizacionDetalle
from apps.facturacion.models import Empresa
from apps.fiscal.models import FormaPago, RegimenFiscal
from apps.inventario.models import Lote
from apps.pagos.models import CuentaPorPagar, Pago
from apps.pagos.services import registrar_pago
from apps.products.models import Almacen, Producto, PuntoVenta, Turno
from apps.proveedores.models import Proveedor
from apps.traspasos.models import Traspaso, TraspasoDetalle, TraspasoLote
from apps.traspasos.services import recibir_traspaso
from apps.ventas.models import Venta, VentaDetalleLote

User = get_user_model()

PDF = b"%PDF-1.4\n%prueba\n"


class ArchivosProtegidosTests(TestCase):
    """B11 (docs/AUDITORIA.md): /media/ estaba exento del login y servía
    cualquier comprobante a quien conociera la URL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor",
            regimen_fiscal=regimen,
        )
        orden = OrdenCompra.objects.create(
            proveedor=proveedor, fecha_orden=date(2026, 9, 1), estatus=OrdenCompra.Estatus.RECIBIDA,
        )
        cls.cuenta = CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("100.00"),
            fecha_emision=date(2026, 9, 2), fecha_vencimiento=date(2026, 10, 2),
        )
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.pagos = User.objects.create_user(username="pagos", password="S3guridad!2026")
        cls.pagos.groups.add(Group.objects.get(name="Pagos"))
        cls.mostrador = User.objects.create_user(username="mostrador", password="S3guridad!2026")
        cls.mostrador.groups.add(Group.objects.get(name="Mostrador y Cotización"))

    def _pago_con_comprobante(self, nombre="transferencia.pdf", contenido=PDF):
        return Pago.objects.create(
            cuenta_por_pagar=self.cuenta, fecha_pago=date(2026, 9, 3), monto_pagado=Decimal("10.00"),
            forma_pago=self.efectivo, comprobante=SimpleUploadedFile(nombre, contenido),
        )

    def test_el_comprobante_se_guarda_en_una_ruta_no_adivinable(self):
        pago = self._pago_con_comprobante()
        carpeta, aleatorio, nombre = pago.comprobante.name.rsplit("/", 2)
        self.assertEqual(carpeta, "pagos/comprobantes")
        self.assertEqual(len(aleatorio), 32)
        self.assertEqual(nombre, "transferencia.pdf")
        self.assertEqual(RutaAleatoria("pagos/comprobantes"), RutaAleatoria("pagos/comprobantes/"))

    def test_sin_sesion_redirige_al_login(self):
        pago = self._pago_con_comprobante()
        respuesta = self.client.get(pago.comprobante.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_con_permiso_del_registro_lo_descarga(self):
        pago = self._pago_con_comprobante()
        self.client.force_login(self.pagos)

        respuesta = self.client.get(pago.comprobante.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(b"".join(respuesta.streaming_content), PDF)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertTrue(respuesta["Content-Disposition"].startswith("inline"))
        self.assertEqual(respuesta["Cache-Control"], "private, no-store")

    def test_sin_permiso_del_registro_responde_404(self):
        pago = self._pago_con_comprobante()
        self.client.force_login(self.mostrador)
        self.assertEqual(self.client.get(pago.comprobante.url).status_code, 404)

    def test_un_archivo_que_ningun_registro_reconoce_no_se_sirve(self):
        admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        pago = self._pago_con_comprobante()
        url = pago.comprobante.url
        Pago.objects.filter(pk=pago.pk).update(comprobante="")
        self.client.force_login(admin)

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get("/media/../config/settings/base.py").status_code, 404)
        self.assertEqual(self.client.get("/media/otra-carpeta/archivo.pdf").status_code, 404)

    def test_un_html_subido_se_descarga_nunca_se_muestra(self):
        pago = self._pago_con_comprobante(nombre="pagina.html", contenido=b"<script>alert(1)</script>")
        self.client.force_login(self.pagos)

        respuesta = self.client.get(pago.comprobante.url)

        self.assertTrue(respuesta["Content-Disposition"].startswith("attachment"))
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")

    def test_con_x_accel_redirect_django_solo_autoriza(self):
        pago = self._pago_con_comprobante()
        self.client.force_login(self.pagos)

        with self.settings(MEDIA_X_ACCEL_REDIRECT="/_media_protegida/"):
            respuesta = self.client.get(pago.comprobante.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["X-Accel-Redirect"], f"/_media_protegida/{pago.comprobante.name}")
        self.assertEqual(respuesta.content, b"")


class UrlDeRegresoTests(TestCase):
    """B12 (docs/AUDITORIA.md): `next` se usaba sin validar."""

    def _request(self, **post):
        return RequestFactory().post("/productos/1/editar/", post)

    def test_acepta_rutas_del_mismo_sitio(self):
        self.assertEqual(url_de_regreso(self._request(next="/productos/?q=croqueta"), "/x/"), "/productos/?q=croqueta")

    def test_acepta_la_url_completa_del_mismo_sitio(self):
        self.assertEqual(url_de_regreso(self._request(next="http://testserver/pagos/"), "/x/"), "http://testserver/pagos/")

    def test_rechaza_otro_sitio_y_javascript(self):
        for malicioso in ("https://evil.example/", "//evil.example/", "javascript:alert(1)", "https:evil.example"):
            self.assertEqual(url_de_regreso(self._request(next=malicioso), "/productos/"), "/productos/", malicioso)


# --- Fase 3: doble envío y concurrencia ----------------------------------

class EscenarioVenta:
    """Datos mínimos para registrar ventas en caja. Crea todo lo que usa (no
    depende de los catálogos que siembran las migraciones), así sirve igual
    en TestCase que en TransactionTestCase, que vacía la base entre pruebas."""

    def crear_escenario(self, existencias=(Decimal("10"),)):
        self.sucursal = Almacen.objects.create(nombre="Sucursal", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        self.caja = PuntoVenta.objects.create(almacen=self.sucursal, codigo="C1", numero=1, nombre="Caja 1")
        self.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        Turno.objects.create(punto_venta=self.caja, usuario=self.admin)
        self.cliente = Cliente.objects.create(nombre="Cliente")
        self.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        self.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_venta=Decimal("50.00"))
        self.lotes = [
            Lote.objects.create(
                producto=self.producto, almacen=self.sucursal, fecha_ingreso=date(2026, 1, 1) + timedelta(days=i),
                costo_unitario=Decimal("30.00"), cantidad_inicial=cantidad, cantidad_disponible=cantidad,
            )
            for i, cantidad in enumerate(existencias)
        ]

    def datos_venta(self, cantidad="1", token=None):
        datos = {
            "cliente": self.cliente.pk, "forma_pago": self.efectivo.pk, "referencia_pago": "",
            "efectivo_recibido": "", "observaciones": "",
            "detalles-TOTAL_FORMS": "1", "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0", "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-producto": self.producto.pk, "detalles-0-cantidad": cantidad,
            "detalles-0-precio_unitario": "1",
            "pagos-TOTAL_FORMS": "0", "pagos-INITIAL_FORMS": "0",
            "pagos-MIN_NUM_FORMS": "0", "pagos-MAX_NUM_FORMS": "1000",
        }
        if token is not None:
            datos["token_envio"] = str(token)
        return datos


class EnvioUnicoTests(EscenarioVenta, TestCase):
    """B15/B16 (docs/AUDITORIA.md): un doble clic o una recarga registraba
    la misma operación dos veces."""

    def setUp(self):
        self.crear_escenario()
        self.client.force_login(self.admin)
        self.url = reverse("ventas:venta-create")

    def test_el_formulario_trae_el_token_y_lo_conserva_al_mostrar_errores(self):
        self.assertContains(self.client.get(self.url), 'name="token_envio"')
        token = uuid.uuid4()
        respuesta = self.client.post(self.url, self.datos_venta(cantidad="999", token=token))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'value="{token}"')

    def test_el_mismo_formulario_dos_veces_registra_una_sola_venta(self):
        token = uuid.uuid4()
        primera = self.client.post(self.url, self.datos_venta(token=token))
        venta = Venta.objects.get()
        segunda = self.client.post(self.url, self.datos_venta(token=token))

        self.assertEqual(Venta.objects.count(), 1)
        self.assertEqual(primera["Location"], reverse("ventas:venta-ticket", args=[venta.pk]))
        self.assertEqual(segunda["Location"], reverse("ventas:venta-ticket", args=[venta.pk]))
        self.assertIn("ya se había registrado", " ".join(str(m) for m in get_messages(segunda.wsgi_request)))

    def test_un_intento_fallido_no_consume_el_token(self):
        token = uuid.uuid4()
        fallido = self.client.post(self.url, self.datos_venta(cantidad="999", token=token))
        self.assertEqual(fallido.status_code, 200)
        self.assertFalse(EnvioUnico.objects.exists())

        self.client.post(self.url, self.datos_venta(cantidad="1", token=token))
        self.assertEqual(Venta.objects.count(), 1)

    def test_sin_token_se_procesa_como_siempre(self):
        self.client.post(self.url, self.datos_venta())
        self.client.post(self.url, self.datos_venta())
        self.assertEqual(Venta.objects.count(), 2)

    def test_depurar_borra_solo_los_tokens_viejos(self):
        viejo = EnvioUnico.objects.create(token=uuid.uuid4(), usuario=self.admin, ruta="/x/")
        EnvioUnico.objects.filter(pk=viejo.pk).update(creado=timezone.now() - timedelta(days=30))
        reciente = EnvioUnico.objects.create(token=uuid.uuid4(), usuario=self.admin, ruta="/x/")

        call_command("depurar_envios_unicos", stdout=StringIO())

        self.assertEqual(list(EnvioUnico.objects.values_list("pk", flat=True)), [reciente.pk])


class PantallasProtegidasTests(EscenarioVenta, TestCase):
    """Las 12 pantallas protegidas contra doble envío (decisión del
    usuario, Fase 3) traen su token en el formulario principal -y solo ahí-:
    si una plantilla lo pierde, la protección del servidor no aplica."""

    def setUp(self):
        from apps.cobros.models import CuentaPorCobrar
        from apps.compras.models import OrdenCompraDetalle
        from apps.pedidos.models import Pedido, PedidoDetalle
        from apps.ventas.models import VentaDetalle

        self.crear_escenario()
        self.admin.groups.add(Group.objects.get(name="Gastos"))  # Gastos es estricto: ni el admin entra sin él
        self.client.force_login(self.admin)

        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General", "aplica_moral": True}
        )[0]
        proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor",
            regimen_fiscal=regimen,
        )
        self.cuentas = []
        for _ in range(2):
            orden = OrdenCompra.objects.create(
                proveedor=proveedor, fecha_orden=date(2026, 9, 1), estatus=OrdenCompra.Estatus.RECIBIDA,
            )
            self.cuentas.append(CuentaPorPagar.objects.create(
                orden_compra=orden, monto_total=Decimal("100.00"),
                fecha_emision=date(2026, 9, 2), fecha_vencimiento=date(2026, 10, 2),
            ))
        self.por_recibir = OrdenCompra.objects.create(
            proveedor=proveedor, fecha_orden=date(2026, 9, 1), estatus=OrdenCompra.Estatus.ENVIADA,
        )
        OrdenCompraDetalle.objects.create(
            orden_compra=self.por_recibir, producto=self.producto, cantidad=5, precio_unitario=Decimal("30"),
        )

        self.venta = Venta.objects.create(cliente=self.cliente, almacen=self.sucursal, forma_pago=self.efectivo)
        VentaDetalle.objects.create(venta=self.venta, producto=self.producto, cantidad=1, precio_unitario=50)
        self.cuenta_cobrar = CuentaPorCobrar.objects.create(
            venta=self.venta, monto_total=Decimal("50.00"),
            fecha_emision=date(2026, 9, 2), fecha_vencimiento=date(2026, 10, 2),
        )
        self.cotizacion = Cotizacion.objects.create(cliente=self.cliente, almacen=self.sucursal, punto_venta=self.caja)
        CotizacionDetalle.objects.create(cotizacion=self.cotizacion, producto=self.producto, cantidad=1, precio_unitario=50)
        self.pedido = Pedido.objects.create(cliente=self.cliente, almacen=self.sucursal, punto_venta=self.caja)
        PedidoDetalle.objects.create(pedido=self.pedido, producto=self.producto, cantidad=1, precio_unitario=50)

    def test_cada_pantalla_trae_un_solo_token(self):
        pantallas = {
            "venta": reverse("ventas:venta-create"),
            "convertir cotización": reverse("cotizaciones:cotizacion-convertir", args=[self.cotizacion.pk]),
            "convertir pedido": reverse("pedidos:pedido-convertir", args=[self.pedido.pk]),
            "pago": reverse("pagos:pago-registrar", args=[self.cuentas[0].pk]),
            "cobro": reverse("cobros:cobro-registrar", args=[self.cuenta_cobrar.pk]),
            "devolución": reverse("ventas:venta-devolver", args=[self.venta.pk]),
            "recepción": reverse("compras:orden-recibir", args=[self.por_recibir.pk]),
            "pedido": reverse("pedidos:pedido-create"),
            "gasto": reverse("gastos:gasto-create"),
            "orden de compra": reverse("compras:orden-create"),
            "traspaso": reverse("traspasos:traspaso-create"),
        }
        for nombre, url in pantallas.items():
            with self.subTest(nombre):
                self.assertContains(self.client.get(url), 'name="token_envio"', count=1)

        pago_multiple = self.client.post(
            reverse("pagos:pago-multiple-preparar"), {"cuenta_ids": [c.pk for c in self.cuentas]}
        )
        self.assertContains(pago_multiple, 'name="token_envio"', count=1)


def en_paralelo(*tareas, timeout=30):
    """Corre `tareas` en hilos (cada uno con su propia conexión a la base)
    que arrancan al mismo tiempo. Devuelve (resultados, errores)."""
    barrera = threading.Barrier(len(tareas))
    resultados, errores = [None] * len(tareas), [None] * len(tareas)

    def correr(indice, tarea):
        try:
            barrera.wait(timeout)
            resultados[indice] = tarea()
        except Exception as e:  # noqa: BLE001 - se reporta al hilo principal
            errores[indice] = e
        finally:
            connection.close()

    hilos = [threading.Thread(target=correr, args=(i, tarea)) for i, tarea in enumerate(tareas)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout)
    return resultados, errores


class ConcurrenciaTests(EscenarioVenta, TransactionTestCase):
    """B14–B18 (docs/AUDITORIA.md) con concurrencia real: dos hilos con su
    propia conexión a Postgres hacen la misma operación al mismo tiempo."""

    def _cliente_web(self):
        cliente = Client()
        cliente.force_login(self.admin)
        return cliente

    def test_mismo_formulario_enviado_dos_veces_a_la_vez_registra_una_venta(self):
        self.crear_escenario()
        datos = self.datos_venta(token=uuid.uuid4())
        url = reverse("ventas:venta-create")

        resultados, errores = en_paralelo(
            lambda: self._cliente_web().post(url, datos).status_code,
            lambda: self._cliente_web().post(url, datos).status_code,
        )

        self.assertEqual(errores, [None, None])
        self.assertEqual(resultados, [302, 302])
        self.assertEqual(Venta.objects.count(), 1)
        self.assertEqual(sum(l.cantidad_disponible for l in Lote.objects.all()), Decimal("9"))

    def test_dos_ventas_a_la_vez_toman_lotes_distintos_sin_fallar(self):
        self.crear_escenario(existencias=(Decimal("1"), Decimal("1")))
        url = reverse("ventas:venta-create")

        resultados, errores = en_paralelo(
            lambda: self._cliente_web().post(url, self.datos_venta(token=uuid.uuid4())).status_code,
            lambda: self._cliente_web().post(url, self.datos_venta(token=uuid.uuid4())).status_code,
        )

        self.assertEqual(errores, [None, None])
        self.assertEqual(resultados, [302, 302])
        self.assertEqual(Venta.objects.count(), 2)
        self.assertEqual(
            sorted(VentaDetalleLote.objects.values_list("lote_id", flat=True)), sorted(l.pk for l in self.lotes)
        )

    def test_convertir_la_misma_cotizacion_a_la_vez_genera_una_venta(self):
        self.crear_escenario()
        cotizacion = Cotizacion.objects.create(
            cliente=self.cliente, almacen=self.sucursal, punto_venta=self.caja,
        )
        CotizacionDetalle.objects.create(cotizacion=cotizacion, producto=self.producto, cantidad=1, precio_unitario=50)
        url = reverse("cotizaciones:cotizacion-convertir", args=[cotizacion.pk])

        resultados, errores = en_paralelo(
            lambda: self._cliente_web().post(url, self.datos_venta(token=uuid.uuid4())).status_code,
            lambda: self._cliente_web().post(url, self.datos_venta(token=uuid.uuid4())).status_code,
        )

        self.assertEqual(errores, [None, None])
        self.assertEqual(sorted(resultados), [200, 302])  # 200 = "ya fue convertida"
        self.assertEqual(Venta.objects.count(), 1)

    def test_recibir_el_mismo_traspaso_a_la_vez_da_de_alta_una_sola_vez(self):
        self.crear_escenario()
        cedis = Almacen.objects.create(nombre="CEDIS", tipo=Almacen.Tipo.CEDIS, numero=9)
        traspaso = Traspaso.objects.create(
            almacen_origen=cedis, almacen_destino=self.sucursal, fecha_envio=date(2026, 9, 1),
            estatus=Traspaso.Estatus.ENVIADO,
        )
        detalle = TraspasoDetalle.objects.create(traspaso=traspaso, producto=self.producto, cantidad=5)
        origen = Lote.objects.create(
            producto=self.producto, almacen=cedis, fecha_ingreso=date(2026, 1, 1), costo_unitario=Decimal("30"),
            cantidad_inicial=5, cantidad_disponible=0,
        )
        TraspasoLote.objects.create(detalle=detalle, lote_origen=origen, cantidad=5)

        _, errores = en_paralelo(lambda: recibir_traspaso(traspaso), lambda: recibir_traspaso(traspaso))

        self.assertEqual(sum(isinstance(e, ValueError) for e in errores), 1, errores)
        self.assertEqual(Lote.objects.filter(almacen=self.sucursal, producto=self.producto).exclude(
            pk__in=[l.pk for l in self.lotes]).count(), 1)

    def test_dos_pagos_a_la_vez_no_rebasan_el_saldo(self):
        self.crear_escenario()
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General", "aplica_moral": True}
        )[0]
        proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor",
            regimen_fiscal=regimen,
        )
        orden = OrdenCompra.objects.create(
            proveedor=proveedor, fecha_orden=date(2026, 9, 1), estatus=OrdenCompra.Estatus.RECIBIDA,
        )
        cuenta = CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("100.00"),
            fecha_emision=date(2026, 9, 2), fecha_vencimiento=date(2026, 10, 2),
        )

        def pagar():
            return registrar_pago(cuenta, date(2026, 9, 3), Decimal("60.00"), self.efectivo)

        _, errores = en_paralelo(pagar, pagar)

        self.assertEqual(sum(isinstance(e, ValidationError) for e in errores), 1, errores)
        self.assertEqual(CuentaPorPagar.objects.get(pk=cuenta.pk).total_pagado, Decimal("60.00"))

    def test_folios_tomados_a_la_vez_nunca_se_repiten(self):
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General", "aplica_moral": True}
        )[0]
        empresa = Empresa.objects.create(
            tipo_persona=Empresa.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Empresa",
            regimen_fiscal=regimen, codigo_postal="86000", siguiente_folio=10,
        )

        def tomar():
            with transaction.atomic():
                return Empresa.objects.get(pk=empresa.pk).tomar_siguiente_folio()

        folios, errores = en_paralelo(tomar, tomar, tomar)

        self.assertEqual(errores, [None, None, None])
        self.assertEqual(sorted(folios), [10, 11, 12])
        self.assertEqual(Empresa.objects.get(pk=empresa.pk).siguiente_folio, 13)


class ParametrosTests(TestCase):
    """apps.core.parametros, la lectura segura de la URL (B28)."""

    def test_ids(self):
        self.assertEqual(id_valido(" 15 "), 15)
        for malo in (None, "", "abc", "-3", "0", "1.5", "²", "١٢", str(2**63)):
            self.assertIsNone(id_valido(malo), malo)
        self.assertEqual(ids_validos("3,abc,,3,7"), [3, 7])
        self.assertEqual(ids_validos(["1", 2, "x", None]), [1, 2])
        self.assertEqual(ids_validos({"no": "lista"}), [])

    def test_fechas(self):
        self.assertEqual(leer_fecha("2026-02-28"), date(2026, 2, 28))
        for mala in ("2026-02-30", "2026-13-01", "hoy", "", None):
            self.assertIsNone(leer_fecha(mala), mala)

    def test_filtrar_por_id(self):
        Almacen.objects.create(nombre="Sucursal", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        todos = Almacen.objects.all()
        self.assertEqual(filtrar_por_id(todos, "pk", "").count(), 1)
        self.assertEqual(filtrar_por_id(todos, "pk", "abc").count(), 0)


class ParametrosInvalidosTests(TestCase):
    """B28 (docs/AUDITORIA.md): un id, fecha o número mal formado en la URL
    o en el JSON daba error 500. El cliente de pruebas relanza cualquier
    excepción de la vista, así que basta con pedir cada pantalla."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_pantallas_con_parametros_invalidos(self):
        malo = {"fecha_desde": "2026-02-30", "fecha_hasta": "2026-99-99", "almacen": "abc"}
        pantallas = [
            ("compras:orden-list", {"proveedor": "abc", **malo}),
            ("compras:analisis-producto", malo),
            ("compras:analisis-anual", {"anio": "²", "producto": "abc", "proveedor": "1e5", "almacen": str(10**30)}),
            ("comisiones:reporte", malo),
            ("comisiones_ruta:reporte", malo),
            ("cobros:cuenta-list", {"periodo": "rango", **malo}),
            ("pagos:cuenta-list", {"periodo": "rango", "forma_pago": "abc", **malo}),
            ("pagos:recibo-list", {"banco": "abc", "forma_pago": "x", **malo}),
            ("pagos:pago-multiple-confirmacion", {"ids": "a,b"}),
            ("inventario:lote-list", {"orden": "abc", "marca": "abc", "categoria": "x", **malo}),
            ("inventario:existencia-list", malo),
            ("inventario:kardex-producto", {"producto": "abc", **malo}),
            ("inventario:existencia-sin-movimiento", {"dias_minimos": "²", **malo}),
            ("inventario:movimiento-costo-list", {"producto": "x", **malo}),
            ("inventario:costeo-producto-list", {"almacen": str(10**30)}),
            ("inventario:movimiento-almacen-list", {"fecha": "2026-02-30", "almacen": "abc"}),
            ("inventario:surtimiento-list", malo),
            ("products:product-list", {"marca": "abc", "subcategoria": "x"}),
            ("api:producto-buscar", {"q": "abc", "almacen": "abc", "cliente": "x", "precio_almacen": "y"}),
            ("api:subcategories-by-category", {"category": "abc"}),
            ("api:promocion-vigente", {"producto": "a", "proveedor": "b", "fecha": "2026-02-30"}),
        ]
        for nombre, parametros in pantallas:
            with self.subTest(nombre):
                respuesta = self.client.get(reverse(nombre), parametros)
                self.assertIn(respuesta.status_code, (200, 302), nombre)

    def test_json_y_formularios_con_ids_invalidos(self):
        precios = self.client.post(
            reverse("api:producto-precios-por-cliente"),
            {"ids": ["a", None], "cliente": "x", "precio_almacen": "y"}, content_type="application/json",
        )
        self.assertEqual(precios.json(), {"precios": {}})
        lista = self.client.post(reverse("api:producto-precios-por-cliente"), [1, 2], content_type="application/json")
        self.assertEqual(lista.status_code, 200)
        skus = self.client.post(
            reverse("api:producto-resolver-skus"), {"skus": ["A"], "almacen": "abc"}, content_type="application/json",
        )
        self.assertEqual(skus.status_code, 400)
        self.assertEqual(self.client.post(reverse("products:turno-abrir"), {"punto_venta": "abc"}).status_code, 404)
        multiple = self.client.post(reverse("pagos:pago-multiple-preparar"), {"cuenta_ids": ["a", "b"]})
        self.assertRedirects(multiple, reverse("pagos:cuenta-list"), fetch_redirect_response=False)

    def test_el_filtro_de_subcategoria_no_inyecta_codigo(self):
        # El valor se pintaba dentro del x-data de Alpine (B32).
        respuesta = self.client.get(reverse("products:product-list"), {"categoria": "1", "subcategoria": "';alert(1)//"})
        self.assertNotContains(respuesta, "alert(1)")


class SinJavaScriptEnLineaTests(TestCase):
    """B32 (docs/AUDITORIA.md): la CSP ya no permite scripts en línea; si una
    plantilla vuelve a traer uno, deja de funcionar en el navegador sin
    avisar. Esta prueba lo detecta antes."""

    def test_la_csp_no_permite_scripts_en_linea(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        politica = self.client.get(reverse("home"))["Content-Security-Policy"]
        script_src = next(d for d in politica.split(";") if d.strip().startswith("script-src"))
        self.assertNotIn("unsafe-inline", script_src)

    def test_ninguna_plantilla_trae_scripts_ni_manejadores_en_linea(self):
        import re
        from pathlib import Path

        from django.conf import settings

        script_en_linea = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I)
        manejador = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.I)
        raiz = Path(settings.BASE_DIR)
        hallazgos = []
        for plantilla in [*raiz.glob("apps/*/templates/**/*.html"), *raiz.glob("templates/**/*.html")]:
            texto = plantilla.read_text(encoding="utf-8")
            for patron in (script_en_linea, manejador):
                for m in patron.finditer(texto):
                    # json_script genera <script type="application/json">, que no se ejecuta.
                    if "application/json" not in m.group(0):
                        hallazgos.append(f"{plantilla.relative_to(raiz)}: {m.group(0).strip()}")
        self.assertEqual(hallazgos, [])


class EstaticosDeProduccionTests(TestCase):
    """B26 (docs/AUDITORIA.md): producción usaba un setting que Django 5.2 ya
    ignora, así que los estáticos no se versionaban. Con el almacenamiento
    real de producción (leído de config/settings/prod.py), collectstatic
    debe terminar y cada {% static %} de las plantillas debe estar en el
    manifiesto: si falta uno, en producción esa página da error 500."""

    def _storages_de_produccion(self):
        import ast
        from pathlib import Path

        from django.conf import settings

        arbol = ast.parse(Path(settings.BASE_DIR, "config", "settings", "prod.py").read_text(encoding="utf-8"))
        nombres = {n.targets[0].id for n in arbol.body if isinstance(n, ast.Assign)}
        self.assertNotIn("STATICFILES_STORAGE", nombres)
        storages = next(
            n.value for n in arbol.body if isinstance(n, ast.Assign) and n.targets[0].id == "STORAGES"
        )
        return ast.literal_eval(storages)

    def test_collectstatic_y_manifiesto(self):
        import re
        from pathlib import Path

        from django.conf import settings
        from django.contrib.staticfiles.storage import staticfiles_storage

        storages = self._storages_de_produccion()
        self.assertIn("Manifest", storages["staticfiles"]["BACKEND"])
        raiz = Path(settings.BASE_DIR)
        referencias = set()
        for plantilla in [*raiz.glob("apps/*/templates/**/*.html"), *raiz.glob("templates/**/*.html")]:
            referencias |= set(re.findall(r"""\{%\s*static\s+['"]([^'"]+)['"]""", plantilla.read_text(encoding="utf-8")))

        destino = tempfile.mkdtemp()
        try:
            with override_settings(STORAGES=storages, STATIC_ROOT=destino, DEBUG=False):
                call_command("collectstatic", interactive=False, verbosity=0)
                faltantes = []
                for referencia in sorted(referencias):
                    try:
                        staticfiles_storage.url(referencia)
                    except ValueError:
                        faltantes.append(referencia)
                self.assertEqual(faltantes, [])
                # La fuente de Tailwind no se publica (ver config/estaticos.py).
                self.assertFalse(Path(destino, "src", "input.css").exists())
        finally:
            shutil.rmtree(destino, ignore_errors=True)


class FiltrosRecordadosTests(TestCase):
    """Decisión del usuario: los filtros de un listado se conservan al volver
    a la pantalla (apps.core.filtros_recordados)."""

    def setUp(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        self.url = reverse("products:product-list")

    def test_volver_sin_filtros_reaplica_los_ultimos_y_avisa(self):
        self.client.get(self.url, {"q": "croqueta", "marca": "", "page": "3"})

        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, f"{self.url}?q=croqueta", fetch_redirect_response=False)

        restaurada = self.client.get(f"{self.url}?q=croqueta")
        self.assertContains(restaurada, "Se aplicaron los filtros que usaste la última vez.")
        self.assertContains(restaurada, f"{self.url}?limpiar_filtros=1")
        # El aviso solo sale en la vuelta que restauró los filtros.
        self.assertNotContains(self.client.get(f"{self.url}?q=croqueta"), "Se aplicaron los filtros")

    def test_limpiar_filtros_los_borra(self):
        self.client.get(self.url, {"q": "croqueta"})
        respuesta = self.client.get(self.url, {"limpiar_filtros": "1"})
        self.assertRedirects(respuesta, self.url, fetch_redirect_response=False)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_enviar_el_formulario_vacio_tambien_limpia(self):
        self.client.get(self.url, {"q": "croqueta"})
        self.client.get(self.url, {"q": "", "marca": ""})
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_cada_pantalla_guarda_sus_propios_filtros(self):
        self.client.get(self.url, {"q": "croqueta"})
        url_proveedores = reverse("proveedores:supplier-list")
        self.assertEqual(self.client.get(url_proveedores).status_code, 200)

    def test_ventas_no_recuerda_el_dia_para_abrir_siempre_en_hoy(self):
        url = reverse("ventas:venta-list")
        self.client.get(url, {"fecha": "2026-01-15"})
        self.assertEqual(self.client.get(url).status_code, 200)
