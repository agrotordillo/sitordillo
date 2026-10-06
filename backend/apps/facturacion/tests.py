from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlencode

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from urllib3.exceptions import MaxRetryError, NewConnectionError

from apps.clientes.models import Cliente
from apps.facturacion import factura_service
from apps.facturacion.facturama_client import FacturamaError, _fallo_antes_de_enviar
from apps.facturacion.models import Factura, FacturaGlobal
from apps.fiscal.models import FormaPago, MetodoPago, UsoCFDI
from apps.products.models import Almacen, Producto, PuntoVenta, Turno
from apps.ventas.models import Venta

User = get_user_model()

RESPUESTA_FACTURAMA = {
    "Id": "fct-123",
    "Serie": "F",
    "Folio": "88",
    "Complement": {"TaxStamp": {"Uuid": "11111111-2222-3333-4444-555555555555"}},
}


class TimbradoTests(TestCase):
    """B04 (docs/AUDITORIA.md): una factura se podía timbrar dos veces -ya
    timbrada, o con doble clic- y un fallo después de timbrar dejaba el CFDI
    sin registrar, listo para duplicarse al reintentar."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.cliente = Cliente.objects.create(nombre="Cliente Prueba")
        cls.efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.uso = UsoCFDI.objects.get_or_create(clave="G03", defaults={"descripcion": "Gastos en general"})[0]
        cls.pue = MetodoPago.objects.get_or_create(clave="PUE", defaults={"descripcion": "Pago en una exhibición"})[0]
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

    def setUp(self):
        venta = Venta.objects.create(cliente=self.cliente, almacen=self.sucursal, forma_pago=self.efectivo)
        self.factura = Factura.objects.create(
            venta=venta, serie="A", numero_folio=7, uso_cfdi=self.uso, metodo_pago=self.pue, lugar_expedicion="86000",
        )
        parche_payload = mock.patch.object(factura_service, "construir_payload_cfdi", return_value={})
        parche_cliente = mock.patch.object(factura_service, "FacturamaClient")
        parche_payload.start()
        self.api = parche_cliente.start().return_value
        self.api.crear_cfdi.return_value = RESPUESTA_FACTURAMA
        self.addCleanup(mock.patch.stopall)

    def _estatus(self):
        return Factura.objects.get(pk=self.factura.pk).estatus

    def test_timbrar_guarda_el_folio_de_facturama_sin_tocar_el_interno(self):
        factura, _ = factura_service.timbrar_factura(self.factura)

        factura.refresh_from_db()
        self.assertEqual(factura.estatus, Factura.Estatus.TIMBRADA)
        self.assertEqual((factura.serie, factura.numero_folio), ("A", 7))
        self.assertEqual((factura.serie_facturama, factura.folio_facturama), ("F", "88"))
        self.assertEqual(factura.serie_folio, "F-88")
        self.assertEqual(factura.facturama_id, "fct-123")
        self.assertEqual(factura.uuid_fiscal, "11111111-2222-3333-4444-555555555555")

    def test_una_factura_timbrada_no_se_vuelve_a_mandar_a_facturama(self):
        factura_service.timbrar_factura(self.factura)

        with self.assertRaisesMessage(ValueError, "ya está timbrada"):
            factura_service.timbrar_factura(self.factura)
        self.assertEqual(self.api.crear_cfdi.call_count, 1)

    def test_mientras_se_timbra_un_segundo_intento_se_rechaza(self):
        Factura.objects.filter(pk=self.factura.pk).update(estatus=Factura.Estatus.TIMBRANDO)

        with self.assertRaisesMessage(ValueError, "ya se está timbrando"):
            factura_service.timbrar_factura(self.factura)
        self.api.crear_cfdi.assert_not_called()

    def test_un_rechazo_de_facturama_deja_reintentar(self):
        self.api.crear_cfdi.side_effect = FacturamaError("Facturama respondió 400: RFC inválido", status_code=400)

        with self.assertRaises(FacturamaError):
            factura_service.timbrar_factura(self.factura)
        self.assertEqual(self._estatus(), Factura.Estatus.ERROR)

        self.api.crear_cfdi.side_effect = None
        factura_service.timbrar_factura(self.factura)
        self.assertEqual(self._estatus(), Factura.Estatus.TIMBRADA)

    def test_un_fallo_incierto_bloquea_el_reintento_hasta_liberarlo(self):
        self.api.crear_cfdi.side_effect = FacturamaError("Read timed out", incierto=True)

        with self.assertLogs("apps.facturacion.factura_service", level="WARNING"), self.assertRaises(FacturamaError):
            factura_service.timbrar_factura(self.factura)
        factura = Factura.objects.get(pk=self.factura.pk)
        self.assertEqual(factura.estatus, Factura.Estatus.TIMBRANDO)
        self.assertIn("pudo haberse timbrado", factura.mensaje_error)

        with self.assertRaisesMessage(ValueError, "ya se está timbrando"):
            factura_service.timbrar_factura(self.factura)
        self.assertEqual(self.api.crear_cfdi.call_count, 1)

    def test_si_falla_al_registrar_el_timbre_se_queda_en_timbrando(self):
        with mock.patch.object(factura_service, "_registrar_timbre", side_effect=RuntimeError("BD caída")):
            with self.assertLogs("apps.facturacion.factura_service", level="ERROR") as logs, \
                    self.assertRaises(RuntimeError):
                factura_service.timbrar_factura(self.factura)
        self.assertEqual(self._estatus(), Factura.Estatus.TIMBRANDO)
        self.assertIn("fct-123", "\n".join(logs.output))

    def test_un_error_armando_el_comprobante_no_llega_a_facturama(self):
        with mock.patch.object(factura_service, "construir_payload_cfdi", side_effect=AttributeError("sin clave SAT")):
            with self.assertRaisesMessage(ValueError, "sin clave SAT"):
                factura_service.timbrar_factura(self.factura)
        self.assertEqual(self._estatus(), Factura.Estatus.ERROR)
        self.api.crear_cfdi.assert_not_called()

    def test_liberar_solo_cuando_ya_no_puede_estar_en_curso(self):
        Factura.objects.filter(pk=self.factura.pk).update(estatus=Factura.Estatus.TIMBRANDO, updated_at=timezone.now())
        with self.assertRaisesMessage(ValueError, "todavía puede estar en curso"):
            factura_service.liberar_timbrado(Factura, self.factura)

        Factura.objects.filter(pk=self.factura.pk).update(updated_at=timezone.now() - timedelta(minutes=5))
        factura_service.liberar_timbrado(Factura, self.factura)
        self.assertEqual(self._estatus(), Factura.Estatus.ERROR)

    def test_vista_timbrar_ya_timbrada_avisa_sin_llamar_a_facturama(self):
        Factura.objects.filter(pk=self.factura.pk).update(estatus=Factura.Estatus.TIMBRADA, facturama_id="previo")
        self.client.force_login(self.admin)

        respuesta = self.client.post(reverse("facturacion:factura-timbrar", args=[self.factura.pk]), follow=True)

        self.assertContains(respuesta, "ya está timbrada")
        self.api.crear_cfdi.assert_not_called()
        self.assertEqual(Factura.objects.get(pk=self.factura.pk).facturama_id, "previo")

    def test_liberar_es_exclusivo_del_administrador(self):
        Factura.objects.filter(pk=self.factura.pk).update(
            estatus=Factura.Estatus.TIMBRANDO, updated_at=timezone.now() - timedelta(minutes=5),
        )
        url = reverse("facturacion:factura-liberar-timbrado", args=[self.factura.pk])
        facturacion = User.objects.create_user(username="facturacion", password="S3guridad!2026")
        facturacion.groups.add(Group.objects.get(name="Facturación"))

        self.client.force_login(facturacion)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self._estatus(), Factura.Estatus.TIMBRANDO)

        self.client.force_login(self.admin)
        self.client.post(url)
        self.assertEqual(self._estatus(), Factura.Estatus.ERROR)

    def test_las_pantallas_muestran_el_estado_timbrando_y_la_opcion_de_liberar(self):
        Factura.objects.filter(pk=self.factura.pk).update(
            estatus=Factura.Estatus.TIMBRANDO, mensaje_error=factura_service.MENSAJE_TIMBRADO_INCIERTO,
        )
        caja = PuntoVenta.objects.create(almacen=self.sucursal, codigo="C1", numero=1, nombre="Caja 1")
        global_ = FacturaGlobal.objects.create(
            turno=Turno.objects.create(punto_venta=caja, usuario=self.admin), serie="AG", numero_folio=8,
            metodo_pago=self.pue, forma_pago=self.efectivo, lugar_expedicion="86000", periodo_mes="10",
            periodo_anio=2026, estatus=FacturaGlobal.Estatus.TIMBRANDO,
        )
        self.client.force_login(self.admin)

        lista = self.client.get(reverse("facturacion:factura-list"))
        self.assertContains(lista, "Timbrando")
        self.assertContains(lista, reverse("facturacion:factura-liberar-timbrado", args=[self.factura.pk]))
        self.assertNotContains(lista, reverse("facturacion:factura-timbrar", args=[self.factura.pk]))

        detalle = self.client.get(reverse("facturacion:factura-global-detalle", args=[global_.pk]))
        self.assertContains(detalle, "AG-8")
        self.assertContains(detalle, reverse("facturacion:factura-global-liberar-timbrado", args=[global_.pk]))
        self.assertEqual(self.client.get(reverse("facturacion:factura-global-list")).status_code, 200)

    def test_cancelar_una_factura_sin_timbrar_no_llama_a_facturama(self):
        with self.assertRaisesMessage(ValueError, "todavía no está timbrada"):
            factura_service.cancelar_factura(self.factura)
        self.api.cancelar_cfdi.assert_not_called()

    def test_la_factura_global_usa_el_mismo_flujo(self):
        caja = PuntoVenta.objects.create(almacen=self.sucursal, codigo="C1", numero=1, nombre="Caja 1")
        turno = Turno.objects.create(punto_venta=caja, usuario=self.admin)
        global_ = FacturaGlobal.objects.create(
            turno=turno, serie="AG", numero_folio=8, metodo_pago=self.pue, forma_pago=self.efectivo,
            lugar_expedicion="86000", periodo_mes="10", periodo_anio=2026,
        )
        with mock.patch.object(factura_service, "construir_payload_cfdi_global", return_value={}):
            factura_service.timbrar_factura_global(global_)
            with self.assertRaisesMessage(ValueError, "ya está timbrada"):
                factura_service.timbrar_factura_global(global_)

        global_.refresh_from_db()
        self.assertEqual((global_.estatus, global_.serie_folio), (FacturaGlobal.Estatus.TIMBRADA, "F-88"))
        self.assertEqual(self.api.crear_cfdi.call_count, 1)


class CatalogoSATTests(TestCase):
    """B07 (docs/AUDITORIA.md): cualquier usuario con sesión agregaba o
    reescribía claves SAT del catálogo local, cuya descripción se muestra
    después en el formulario de producto."""

    @classmethod
    def setUpTestData(cls):
        cls.mostrador = User.objects.create_user(username="mostrador", password="S3guridad!2026")
        cls.mostrador.groups.add(Group.objects.get(name="Mostrador y Cotización"))
        cls.compras = User.objects.create_user(username="compras", password="S3guridad!2026")
        cls.compras.groups.add(Group.objects.get(name="Compras - Completo"))

    def test_solo_quien_crea_o_edita_productos_agrega_claves(self):
        from apps.fiscal.models import ClaveProdServSAT

        url = reverse("facturacion:buscar-clave-prod-serv")
        datos = {"clave": "99999999", "etiqueta": "<img src=x onerror=alert(1)>"}

        self.client.force_login(self.mostrador)
        self.assertEqual(self.client.post(url, datos).status_code, 403)
        self.assertFalse(ClaveProdServSAT.objects.filter(clave="99999999").exists())

        self.client.force_login(self.compras)
        respuesta = self.client.post(f"{url}?{urlencode({'q': 'a b&c'})}", datos)
        self.assertEqual(respuesta["Location"], f"{url}?q=a+b%26c")
        self.assertTrue(ClaveProdServSAT.objects.filter(clave="99999999").exists())

    def test_la_busqueda_sigue_abierta_pero_sin_boton_de_agregar(self):
        resultados = [{"Value": "10101500", "Name": "Animales vivos de granja"}]
        with mock.patch(
            "apps.facturacion.views.catalogo_sat_views.buscar_claves_prod_serv", return_value=resultados,
        ):
            self.client.force_login(self.mostrador)
            sin_permiso = self.client.get(reverse("facturacion:buscar-clave-prod-serv"), {"q": "animal"})
            self.client.force_login(self.compras)
            con_permiso = self.client.get(reverse("facturacion:buscar-clave-prod-serv"), {"q": "animal"})

        self.assertContains(sin_permiso, "Animales vivos de granja")
        self.assertNotContains(sin_permiso, 'name="etiqueta"')
        self.assertContains(con_permiso, 'name="etiqueta"')


class FacturamaClientTests(TestCase):
    def test_distingue_si_la_solicitud_llego_a_facturama(self):
        sin_conexion = requests.exceptions.ConnectionError(
            MaxRetryError(None, "/3/cfdis", reason=NewConnectionError(None, "Connection refused"))
        )
        self.assertTrue(_fallo_antes_de_enviar(sin_conexion))
        self.assertTrue(_fallo_antes_de_enviar(requests.exceptions.ConnectTimeout()))
        self.assertFalse(_fallo_antes_de_enviar(requests.exceptions.ReadTimeout()))
        self.assertFalse(_fallo_antes_de_enviar(requests.exceptions.ConnectionError("Connection aborted")))

    def test_respuesta_exitosa_ilegible_es_incierta(self):
        from apps.facturacion.facturama_client import FacturamaClient

        respuesta = mock.Mock(status_code=201, text="<html>", content=b"<html>")
        respuesta.json.side_effect = ValueError("no es JSON")
        with mock.patch("apps.facturacion.facturama_client.requests.request", return_value=respuesta):
            with self.assertRaises(FacturamaError) as ctx:
                FacturamaClient().crear_cfdi({})
        self.assertTrue(ctx.exception.incierto)


class DescuentoEnCFDITests(SimpleTestCase):
    """B31 (docs/AUDITORIA.md): con descuento, la línea del CFDI restaba el
    descuento dos veces (la base ya venía neta) y lo mandaba con impuestos.
    En el CFDI todo va sin impuestos: Subtotal antes del descuento,
    Discount aparte y los impuestos sobre Subtotal - Discount."""

    def _detalle(self, precio, cantidad=1, descuento=0, tasa_ieps=None):
        producto = SimpleNamespace(
            TipoIVA=Producto.TipoIVA, tipo_iva=Producto.TipoIVA.GRAVADO, tasa_iva=Decimal("16.00"),
            aplica_ieps=tasa_ieps is not None, tasa_ieps=tasa_ieps, sku="CRQ", nombre="Croqueta",
            clave_prod_serv_sat=SimpleNamespace(clave="10121800"),
            clave_unidad_sat=SimpleNamespace(clave="H87", nombre="Pieza"),
        )
        return SimpleNamespace(
            producto=producto, cantidad=Decimal(cantidad), precio_unitario=Decimal(precio), descuento=Decimal(descuento),
        )

    def test_linea_con_descuento(self):
        item = factura_service._construir_item_cfdi(self._detalle("116.00", descuento=10))
        self.assertEqual((item["Subtotal"], item["Discount"], item["Total"]), (100.0, 10.0, 104.4))
        self.assertEqual(item["UnitPrice"], 100.0)
        [iva] = item["Taxes"]
        self.assertEqual((iva["Base"], iva["Total"]), (90.0, 14.4))

    def test_sin_descuento_no_cambia_nada(self):
        item = factura_service._construir_item_cfdi(self._detalle("116.00"))
        self.assertEqual((item["Subtotal"], item["Discount"], item["Total"]), (100.0, 0.0, 116.0))

    def test_ieps_e_iva_cuadran_con_el_precio_cobrado(self):
        item = factura_service._construir_item_cfdi(self._detalle("125.28", cantidad=2, tasa_ieps=Decimal("8.00")))
        impuestos = {t["Name"]: (t["Base"], t["Total"]) for t in item["Taxes"]}
        self.assertEqual(impuestos, {"IEPS": (200.0, 16.0), "IVA": (216.0, 34.56)})
        self.assertEqual(item["Total"], 250.56)

    def test_linea_de_factura_global_con_descuento(self):
        venta = SimpleNamespace(
            folio="V-1", detalles=SimpleNamespace(select_related=lambda *_: [self._detalle("116.00", descuento=10)]),
        )
        item = factura_service._construir_item_cfdi_global(venta)
        self.assertEqual((item["Subtotal"], item["Discount"], item["Total"]), (100.0, 10.0, 104.4))
        self.assertEqual(item["Taxes"][0]["Base"], 90.0)
