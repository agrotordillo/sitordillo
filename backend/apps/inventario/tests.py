from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AsignacionSucursal
from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.fiscal.models import FormaPago, RegimenFiscal
from apps.inventario.models import Lote, MovimientoAlmacen, MovimientoAlmacenLote, RecetaConversion
from apps.inventario.services import (
    aplicar_movimiento_almacen,
    cancelar_movimiento_almacen,
    corregir_recepcion,
    registrar_conversion,
    registrar_ensamble_paquete,
    registrar_merma_recepcion,
    registrar_salida,
    sugerir_impuestos_de_merma,
)
from apps.pagos.models import CuentaPorPagar, Pago
from apps.products.models import Almacen, PaqueteComponente, Producto
from apps.proveedores.models import Proveedor

User = get_user_model()
Concepto = MovimientoAlmacen.Concepto


class MovimientoAlmacenTests(TestCase):
    """Movimientos manuales de almacén: borrador sin afectar existencias,
    aplicar (entradas al último costo de compra, salidas por FIFO) y
    cancelar regresando a los mismos lotes."""

    @classmethod
    def setUpTestData(cls):
        cls.bodega = Almacen.objects.create(nombre="Bodega Sur", tipo=Almacen.Tipo.CEDIS, numero=1)
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        cls.movil = Almacen.objects.create(nombre="Unidad Móvil 1", tipo=Almacen.Tipo.MOVIL, numero=3)
        cls.producto = Producto.objects.create(
            nombre="Cascarilla 20kg", sku="CASC20", precio_costo=Decimal("90.0000"), precio_venta=Decimal("150.00"),
        )
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Prueba",
            regimen_fiscal=regimen,
        )

        cls.compras = User.objects.create_user(username="compras", password="S3guridad!2026")
        cls.compras.groups.add(Group.objects.get(name="Compras - Completo"))
        cls.almacenista = User.objects.create_user(username="almacenista", password="S3guridad!2026")
        cls.almacenista.groups.add(Group.objects.get(name="Almacén"))

    def _lote(self, almacen, cantidad, fecha_ingreso, costo, **extra):
        return Lote.objects.create(
            producto=self.producto, almacen=almacen, fecha_ingreso=fecha_ingreso,
            costo_unitario=costo, cantidad_inicial=cantidad, cantidad_disponible=cantidad, **extra,
        )

    def _lote_de_compra(self, cantidad, fecha_ingreso, costo):
        orden = OrdenCompra.objects.create(proveedor=self.proveedor, fecha_orden=fecha_ingreso)
        detalle = OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=self.producto, cantidad=cantidad, precio_unitario=costo,
        )
        return self._lote(self.bodega, cantidad, fecha_ingreso, costo, orden_compra_detalle=detalle)

    def _existencia(self, almacen):
        return sum(
            (l.cantidad_disponible for l in Lote.objects.filter(producto=self.producto, almacen=almacen)),
            Decimal("0"),
        )

    def _crear(self, concepto, cantidad, almacen=None, **extra):
        self.client.force_login(self.compras)
        datos = {
            "concepto": concepto,
            "almacen": (almacen or self.bodega).pk,
            "fecha": "2026-10-01",
            "documento_referencia": "",
            "observaciones": "",
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-producto": self.producto.pk,
            "detalles-0-cantidad": str(cantidad),
            **extra,
        }
        return self.client.post(reverse("inventario:movimiento-almacen-create"), datos)

    def _crear_ok(self, concepto, cantidad, almacen=None, **extra):
        respuesta = self._crear(concepto, cantidad, almacen=almacen, **extra)
        self.assertEqual(
            respuesta.status_code, 302, getattr(respuesta, "context", None) and respuesta.context["form"].errors
        )
        return MovimientoAlmacen.objects.latest("id")

    def test_aplicar_o_cancelar_muestra_el_error_del_modelo_en_vez_de_tronar(self):
        # B29 (docs/AUDITORIA.md): solo se atrapaba ValueError.
        movimiento = self._crear_ok(Concepto.ENTRADA_SOBRANTE, 5)
        for nombre, servicio in (
            ("inventario:movimiento-almacen-aplicar", "aplicar_movimiento_almacen"),
            ("inventario:movimiento-almacen-cancelar", "cancelar_movimiento_almacen"),
        ):
            with mock.patch(
                f"apps.inventario.views.movimiento_almacen_views.{servicio}",
                side_effect=ValidationError("Mensaje de validación del modelo."),
            ):
                respuesta = self.client.post(reverse(nombre, args=[movimiento.pk]), follow=True)
            self.assertIn("Mensaje de validación del modelo.", [str(m) for m in respuesta.context["messages"]])

    def test_entrada_sobrante_queda_en_borrador_y_al_aplicar_usa_ultimo_costo_de_compra(self):
        self._lote_de_compra(Decimal("10"), date(2026, 5, 1), Decimal("100.00"))
        self._lote_de_compra(Decimal("10"), date(2026, 5, 12), Decimal("120.00"))
        # Un lote más reciente que NO viene de compra no cuenta como "último costo".
        self._lote(self.bodega, Decimal("1"), date(2026, 6, 1), Decimal("999.00"))

        movimiento = self._crear_ok(Concepto.ENTRADA_SOBRANTE, 5)
        self.assertEqual(movimiento.estado, MovimientoAlmacen.Estado.BORRADOR)
        self.assertEqual(self._existencia(self.bodega), Decimal("21"))

        respuesta = self.client.post(reverse("inventario:movimiento-almacen-aplicar", args=[movimiento.pk]))
        self.assertEqual(respuesta.status_code, 302)

        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, MovimientoAlmacen.Estado.APLICADO)
        self.assertEqual(self._existencia(self.bodega), Decimal("26"))
        detalle = movimiento.detalles.get()
        self.assertEqual(detalle.costo_unitario, Decimal("120.00"))
        lote_nuevo = detalle.lotes.get().lote
        self.assertEqual(lote_nuevo.costo_unitario, Decimal("120.00"))
        self.assertEqual(lote_nuevo.numero_lote, movimiento.folio)

    def test_entrada_sin_compras_previas_usa_costo_de_catalogo(self):
        movimiento = self._crear_ok(Concepto.ENTRADA_REGALIA, 2, proveedor=self.proveedor.pk)
        aplicar_movimiento_almacen(movimiento)
        self.assertEqual(movimiento.detalles.get().costo_unitario, Decimal("90.00"))

    def test_regalia_exige_proveedor(self):
        respuesta = self._crear(Concepto.ENTRADA_REGALIA, 2)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("proveedor", respuesta.context["form"].errors)
        self.assertFalse(MovimientoAlmacen.objects.exists())

    def test_salida_fifo_y_cancelacion_regresa_a_los_mismos_lotes(self):
        viejo = self._lote(self.bodega, Decimal("3"), date(2026, 1, 1), Decimal("100.00"))
        nuevo = self._lote(self.bodega, Decimal("10"), date(2026, 6, 1), Decimal("130.00"))

        movimiento = self._crear_ok(Concepto.SALIDA_FALTANTE, 5)
        aplicar_movimiento_almacen(movimiento)

        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual((viejo.cantidad_disponible, nuevo.cantidad_disponible), (Decimal("0"), Decimal("8")))
        # (3 × 100 + 2 × 130) / 5
        self.assertEqual(movimiento.detalles.get().costo_unitario, Decimal("112.00"))

        respuesta = self.client.post(
            reverse("inventario:movimiento-almacen-cancelar", args=[movimiento.pk]), {"motivo": "Se encontró"}
        )
        self.assertEqual(respuesta.status_code, 302)
        viejo.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual((viejo.cantidad_disponible, nuevo.cantidad_disponible), (Decimal("3"), Decimal("10")))
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, MovimientoAlmacen.Estado.CANCELADO)
        self.assertEqual(movimiento.motivo_cancelacion, "Se encontró")
        detalle = self.client.get(reverse("inventario:movimiento-almacen-detail", args=[movimiento.pk]))
        self.assertContains(detalle, "Salida por faltante")
        self.assertContains(detalle, "Se encontró")

    def test_no_se_cancela_una_entrada_que_ya_se_consumio(self):
        movimiento = self._crear_ok(Concepto.ENTRADA_AJUSTE, 5)
        aplicar_movimiento_almacen(movimiento)
        registrar_salida(self.producto, self.bodega, Decimal("3"))

        with self.assertRaises(ValueError):
            cancelar_movimiento_almacen(movimiento)

        movimiento.refresh_from_db()
        self.assertEqual(movimiento.estado, MovimientoAlmacen.Estado.APLICADO)
        self.assertEqual(self._existencia(self.bodega), Decimal("2"))

    def test_salida_sin_existencia_no_se_guarda(self):
        self._lote(self.bodega, Decimal("2"), date(2026, 1, 1), Decimal("100.00"))
        respuesta = self._crear(Concepto.SALIDA_CONSUMO, 5)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertFalse(MovimientoAlmacen.objects.exists())

    def test_devolucion_movil_regresa_los_mismos_lotes_al_destino(self):
        origen = self._lote(
            self.movil, Decimal("5"), date(2026, 9, 30), Decimal("300.00"),
            numero_lote="L-77", fecha_caducidad=date(2027, 3, 1),
        )
        movimiento = self._crear_ok(
            Concepto.SALIDA_DEVOLUCION_MOVIL, 1, almacen=self.movil, almacen_destino=self.sucursal.pk,
        )
        aplicar_movimiento_almacen(movimiento)

        origen.refresh_from_db()
        self.assertEqual(origen.cantidad_disponible, Decimal("4"))
        afectado = MovimientoAlmacenLote.objects.get(detalle__movimiento=movimiento)
        destino = afectado.lote_destino
        self.assertEqual(destino.almacen, self.sucursal)
        self.assertEqual(destino.cantidad_disponible, Decimal("1"))
        self.assertEqual(
            (destino.costo_unitario, destino.numero_lote, destino.fecha_caducidad),
            (Decimal("300.00"), "L-77", date(2027, 3, 1)),
        )

        cancelar_movimiento_almacen(movimiento)
        origen.refresh_from_db()
        destino.refresh_from_db()
        self.assertEqual((origen.cantidad_disponible, destino.cantidad_disponible), (Decimal("5"), Decimal("0")))

    def test_devolucion_movil_solo_sale_de_un_almacen_movil(self):
        self._lote(self.bodega, Decimal("5"), date(2026, 1, 1), Decimal("100.00"))
        respuesta = self._crear(Concepto.SALIDA_DEVOLUCION_MOVIL, 1, almacen_destino=self.sucursal.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("almacen", respuesta.context["form"].errors)

    def test_relacionar_con_el_movimiento_que_lo_antecede_por_folio(self):
        temporal = self._crear_ok(Concepto.ENTRADA_AJUSTE, 10)
        aplicar_movimiento_almacen(temporal)
        regulariza = self._crear_ok(Concepto.SALIDA_AJUSTE, 10, movimiento_relacionado_folio=temporal.folio.lower())
        self.assertEqual(regulariza.movimiento_relacionado, temporal)
        self.assertEqual(list(temporal.movimientos_derivados.all()), [regulariza])
        detalle = self.client.get(reverse("inventario:movimiento-almacen-detail", args=[temporal.pk]))
        self.assertContains(detalle, regulariza.folio)
        editar = self.client.get(reverse("inventario:movimiento-almacen-update", args=[regulariza.pk]))
        self.assertContains(editar, temporal.folio)

    def test_filtros_de_la_lista(self):
        self._lote(self.bodega, Decimal("50"), date(2026, 1, 1), Decimal("100.00"))
        hoy = self._crear_ok(Concepto.SALIDA_MERMA, 1)
        ayer = self._crear_ok(Concepto.ENTRADA_SOBRANTE, 1, fecha="2026-09-30")
        aplicar_movimiento_almacen(ayer)
        url = reverse("inventario:movimiento-almacen-list")

        def folios(**filtros):
            respuesta = self.client.get(url, filtros)
            return {m.folio for m in respuesta.context["movimientos"]}

        self.assertEqual(folios(), {hoy.folio, ayer.folio})
        self.assertEqual(folios(fecha_op="igual", fecha="2026-10-01"), {hoy.folio})
        self.assertEqual(folios(fecha_op="hasta", fecha="2026-09-30"), {ayer.folio})
        self.assertEqual(folios(fecha_op="entre", fecha="2026-09-01", fecha_fin="2026-10-31"), {hoy.folio, ayer.folio})
        self.assertEqual(folios(estado="aplicado"), {ayer.folio})
        self.assertEqual(folios(concepto=Concepto.SALIDA_MERMA), {hoy.folio})
        self.assertEqual(folios(almacen=self.sucursal.pk), set())

    def test_solo_compras_o_admin(self):
        self.client.force_login(self.almacenista)
        self.assertEqual(self.client.get(reverse("inventario:movimiento-almacen-list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventario:movimiento-almacen-create")).status_code, 403)

        self.client.force_login(self.compras)
        self.assertEqual(self.client.get(reverse("inventario:movimiento-almacen-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("inventario:movimiento-almacen-create")).status_code, 200)


class CostoDeLoteTests(TestCase):
    """B05 (docs/AUDITORIA.md): Producto.precio_costo tiene 4 decimales y
    Lote.costo_unitario 2; dar de alta un lote desde el costo de catálogo
    tronaba en Lote.full_clean() aun con ceros a la derecha."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)

    def _lote(self, producto, cantidad, costo):
        return Lote.objects.create(
            producto=producto, almacen=self.sucursal, fecha_ingreso=date(2026, 1, 1),
            costo_unitario=costo, cantidad_inicial=cantidad, cantidad_disponible=cantidad,
        )

    def test_el_lote_redondea_el_costo_antes_de_validarlo(self):
        producto = Producto.objects.create(nombre="Avena", sku="AVE")
        lote = Lote(
            producto=producto, almacen=self.sucursal, fecha_ingreso=date(2026, 1, 1),
            costo_unitario=Decimal("12.3450"), cantidad_inicial=1, cantidad_disponible=1,
        )
        lote.full_clean()
        self.assertEqual(lote.costo_unitario, Decimal("12.35"))

    def test_conversion_con_costo_de_catalogo_de_4_decimales(self):
        origen = Producto.objects.create(nombre="Maíz 40kg", sku="M40", precio_costo=Decimal("5.0000"))
        destino = Producto.objects.create(nombre="Maíz 2kg", sku="M2", precio_costo=Decimal("12.3456"))
        receta = RecetaConversion.objects.create(
            producto_origen=origen, producto_destino=destino, cantidad_origen=1, cantidad_destino=2,
        )
        self._lote(origen, Decimal("10"), Decimal("5.00"))

        conversion = registrar_conversion(RecetaConversion.objects.get(pk=receta.pk), self.sucursal, Decimal("1"))

        lote_destino = Lote.objects.get(producto=destino)
        self.assertEqual(lote_destino.costo_unitario, Decimal("12.35"))
        self.assertEqual(lote_destino.cantidad_disponible, Decimal("2"))
        # El valor generado se calcula con el mismo costo con el que queda el lote.
        self.assertEqual(conversion.valor_generado, Decimal("24.70"))

    def test_ensamble_con_costo_unitario_de_mas_de_2_decimales(self):
        # Desde B25 el paquete se costea con lo que costaron sus componentes:
        # por FIFO 1 x 10.00 + 2 x 10.01 = 30.02 entre 3 paquetes da
        # 10.0066..., que el lote guarda como 10.01.
        componente = Producto.objects.create(nombre="Bolsa", sku="BOL", precio_costo=Decimal("10.0000"))
        paquete = Producto.objects.create(
            nombre="Combo", sku="CMB", tipo=Producto.TipoProducto.PAQUETE, almacen=self.sucursal,
            precio_costo=Decimal("30.0050"),
        )
        PaqueteComponente.objects.create(paquete=paquete, producto_componente=componente, cantidad=1)
        self._lote(componente, Decimal("1"), Decimal("10.00"))
        Lote.objects.create(
            producto=componente, almacen=self.sucursal, fecha_ingreso=date(2026, 1, 2),
            costo_unitario=Decimal("10.01"), cantidad_inicial=5, cantidad_disponible=5,
        )

        ensamble = registrar_ensamble_paquete(Producto.objects.get(pk=paquete.pk), self.sucursal, Decimal("3"))

        self.assertEqual(ensamble.valor_consumido, Decimal("30.02"))
        self.assertEqual(Lote.objects.get(producto=paquete).costo_unitario, Decimal("10.01"))
        self.assertEqual(ensamble.valor_generado, Decimal("30.03"))

    def test_la_vista_de_conversion_muestra_el_error_en_vez_de_tronar(self):
        admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        origen = Producto.objects.create(nombre="Maíz 40kg", sku="M40")
        destino = Producto.objects.create(nombre="Maíz 2kg", sku="M2")
        receta = RecetaConversion.objects.create(
            producto_origen=origen, producto_destino=destino, cantidad_origen=1, cantidad_destino=2,
        )
        self.client.force_login(admin)
        with mock.patch(
            "apps.inventario.views.conversion_views.registrar_conversion",
            side_effect=ValidationError("Mensaje de validación del modelo."),
        ):
            respuesta = self.client.post(reverse("inventario:conversion-create"), {
                "almacen": self.sucursal.pk, "receta": receta.pk, "cantidad_origen": "1",
                "fecha": "2026-10-01", "observaciones": "",
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Mensaje de validación del modelo.", respuesta.context["form"].non_field_errors())


class CorregirRecepcionTests(TestCase):
    """B03 (docs/AUDITORIA.md): corregir una recepción cobraba dos veces la
    mercancía y dejaba la orden como parcial."""

    @classmethod
    def setUpTestData(cls):
        cls.cedis = Almacen.objects.create(nombre="CEDIS", tipo=Almacen.Tipo.CEDIS, numero=1)
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Prueba",
            regimen_fiscal=regimen,
        )
        cls.equivocado = Producto.objects.create(nombre="Alimento A", sku="ALA")
        cls.correcto = Producto.objects.create(nombre="Alimento B", sku="ALB")

    def _orden_recibida(self, cantidad=10, recibida=10):
        orden = OrdenCompra.objects.create(
            proveedor=self.proveedor, fecha_orden=date(2026, 9, 1), estatus=OrdenCompra.Estatus.RECIBIDA,
        )
        detalle = OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=self.equivocado, cantidad=cantidad,
            precio_unitario=Decimal("10.00"), cantidad_recibida=recibida,
        )
        lote = Lote.objects.create(
            producto=self.equivocado, almacen=self.cedis, orden_compra_detalle=detalle, numero_lote="L-1",
            fecha_ingreso=date(2026, 9, 2), costo_unitario=Decimal("9.00"),
            cantidad_inicial=recibida, cantidad_disponible=recibida,
        )
        return orden, detalle, lote

    def test_correccion_completa_conserva_el_total_y_elimina_la_linea_equivocada(self):
        orden, detalle, lote = self._orden_recibida()

        lote_nuevo = corregir_recepcion(lote, Decimal("10"), self.correcto)

        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual(orden.subtotal, Decimal("100.00"))
        self.assertEqual(orden.estatus, OrdenCompra.Estatus.RECIBIDA)
        self.assertFalse(OrdenCompraDetalle.objects.filter(pk=detalle.pk).exists())
        linea = orden.detalles.get()
        self.assertEqual((linea.producto, linea.cantidad, linea.cantidad_recibida), (self.correcto, 10, 10))
        self.assertEqual(lote_nuevo.orden_compra_detalle, linea)
        self.assertEqual(lote_nuevo.cantidad_disponible, Decimal("10"))
        lote.refresh_from_db()
        self.assertEqual(lote.cantidad_disponible, Decimal("0"))
        self.assertIsNone(lote.orden_compra_detalle)

    def test_correccion_parcial_mueve_tambien_lo_ordenado(self):
        orden, detalle, lote = self._orden_recibida()

        corregir_recepcion(lote, Decimal("4"), self.correcto)

        orden = OrdenCompra.objects.get(pk=orden.pk)
        detalle.refresh_from_db()
        self.assertEqual((detalle.cantidad, detalle.cantidad_recibida), (6, 6))
        self.assertEqual(orden.detalles.get(producto=self.correcto).cantidad, 4)
        self.assertEqual(orden.subtotal, Decimal("100.00"))
        self.assertEqual(orden.estatus, OrdenCompra.Estatus.RECIBIDA)

    def test_si_ambos_productos_venian_en_la_orden_la_linea_equivocada_sigue_pendiente(self):
        orden, detalle, lote = self._orden_recibida(cantidad=10, recibida=4)
        OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=self.correcto, cantidad=10, precio_unitario=Decimal("10.00"),
        )

        corregir_recepcion(lote, Decimal("4"), self.correcto)

        detalle.refresh_from_db()
        self.assertEqual((detalle.cantidad, detalle.cantidad_recibida), (10, 0))
        linea_correcta = OrdenCompraDetalle.objects.get(orden_compra=orden, producto=self.correcto)
        self.assertEqual((linea_correcta.cantidad, linea_correcta.cantidad_recibida), (10, 4))
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).estatus, OrdenCompra.Estatus.PARCIAL)

    def test_resincroniza_la_cuenta_por_pagar_y_rechaza_si_ya_tiene_pagos(self):
        orden, _, lote = self._orden_recibida()
        cuenta = CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("100.00"),
            fecha_emision=date(2026, 9, 3), fecha_vencimiento=date(2026, 10, 3),
        )
        OrdenCompraDetalle.objects.filter(orden_compra=orden).update(precio_unitario=Decimal("12.00"))

        corregir_recepcion(lote, Decimal("5"), self.correcto)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.monto_total, Decimal("120.00"))

        Pago.objects.create(
            cuenta_por_pagar=cuenta, fecha_pago=date(2026, 9, 4), monto_pagado=Decimal("10.00"),
            forma_pago=FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0],
        )
        with self.assertRaisesMessage(ValueError, "ya tiene pagos"):
            corregir_recepcion(Lote.objects.get(pk=lote.pk), Decimal("1"), self.correcto)

    def test_no_corrige_lo_que_ya_se_dio_de_baja_como_merma(self):
        _, detalle, lote = self._orden_recibida()
        OrdenCompraDetalle.objects.filter(pk=detalle.pk).update(cantidad_merma=Decimal("8"))

        with self.assertRaisesMessage(ValueError, "solo quedan 2.00 recibidas sin merma"):
            corregir_recepcion(lote, Decimal("3"), self.correcto)


class CosteoPorSucursalTests(TestCase):
    """B10 (docs/AUDITORIA.md): con ?almacen= un usuario restringido veía
    los costos de cualquier sucursal."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal_a = Almacen.objects.create(nombre="Sucursal A", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.sucursal_b = Almacen.objects.create(nombre="Sucursal B", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        cls.en_a = Producto.objects.create(nombre="Producto en A", sku="ENA")
        cls.en_b = Producto.objects.create(nombre="Producto en B", sku="ENB")
        for producto, almacen in ((cls.en_a, cls.sucursal_a), (cls.en_b, cls.sucursal_b)):
            Lote.objects.create(
                producto=producto, almacen=almacen, fecha_ingreso=date(2026, 1, 1), costo_unitario=Decimal("10.00"),
                cantidad_inicial=1, cantidad_disponible=1,
            )
        cls.almacenista = User.objects.create_user(username="almacenista", password="S3guridad!2026")
        cls.almacenista.groups.add(Group.objects.get(name="Almacén"))
        AsignacionSucursal.objects.create(usuario=cls.almacenista, almacen=cls.sucursal_a)

    def _skus(self, **filtros):
        respuesta = self.client.get(reverse("inventario:costeo-producto-list"), filtros)
        self.assertEqual(respuesta.status_code, 200)
        return {p.sku for p in respuesta.context["productos"]}

    def test_el_filtro_de_sucursal_no_salta_la_restriccion(self):
        self.client.force_login(self.almacenista)
        self.assertEqual(self._skus(), {"ENA"})
        self.assertEqual(self._skus(almacen=self.sucursal_a.pk), {"ENA"})
        self.assertEqual(self._skus(almacen=self.sucursal_b.pk), set())
        self.assertEqual(self._skus(almacen="abc"), set())

    def test_sin_restriccion_el_filtro_funciona_igual(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        self.assertEqual(self._skus(), {"ENA", "ENB"})
        self.assertEqual(self._skus(almacen=self.sucursal_b.pk), {"ENB"})


class RecepcionDeCompraTests(TestCase):
    """B23 (docs/AUDITORIA.md): se podía recibir una orden en Borrador, y en
    cualquier almacén aunque el usuario solo opere su sucursal."""

    @classmethod
    def setUpTestData(cls):
        cls.cedis = Almacen.objects.create(nombre="CEDIS", tipo=Almacen.Tipo.CEDIS, numero=1)
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Prueba",
            regimen_fiscal=regimen,
        )
        cls.producto = Producto.objects.create(nombre="Alimento", sku="ALI")
        cls.almacenista = User.objects.create_user(username="almacenista", password="S3guridad!2026")
        cls.almacenista.groups.add(Group.objects.get(name="Almacén"))
        AsignacionSucursal.objects.create(usuario=cls.almacenista, almacen=cls.sucursal)

    def _orden(self, estatus):
        orden = OrdenCompra.objects.create(
            proveedor=self.proveedor, almacen_destino=self.cedis, fecha_orden=date(2026, 9, 1), estatus=estatus,
        )
        detalle = OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=self.producto, cantidad=Decimal("10"), precio_unitario=Decimal("10.00"),
        )
        return orden, detalle

    def _recibir(self, orden, detalle, almacen):
        return self.client.post(reverse("compras:orden-recibir", args=[orden.pk]), {
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-detalle_id": detalle.pk, "form-0-cantidad_recibir": "10", "form-0-costo_unitario": "10.00",
            "form-0-almacen": almacen.pk,
        })

    def test_una_orden_en_borrador_no_se_recibe(self):
        self.assertTrue(self.almacenista.has_perm("inventario.add_lote"))
        self.client.force_login(self.almacenista)
        orden, detalle = self._orden(OrdenCompra.Estatus.BORRADOR)

        for respuesta in (
            self.client.get(reverse("compras:orden-recibir", args=[orden.pk])),
            self._recibir(orden, detalle, self.sucursal),
        ):
            self.assertRedirects(respuesta, reverse("compras:orden-list"), fetch_redirect_response=False)
        self.assertFalse(Lote.objects.exists())

    def test_solo_se_recibe_en_las_sucursales_del_usuario(self):
        self.client.force_login(self.almacenista)
        orden, detalle = self._orden(OrdenCompra.Estatus.ENVIADA)

        respuesta = self.client.get(reverse("compras:orden-recibir", args=[orden.pk]))
        self.assertEqual(list(respuesta.context["formset"].forms[0].fields["almacen"].queryset), [self.sucursal])

        respuesta = self._recibir(orden, detalle, self.cedis)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("almacen", respuesta.context["formset"].forms[0].errors)
        self.assertFalse(Lote.objects.exists())

        respuesta = self._recibir(orden, detalle, self.sucursal)
        self.assertRedirects(respuesta, reverse("compras:orden-list"), fetch_redirect_response=False)
        self.assertEqual(Lote.objects.get().almacen, self.sucursal)
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).estatus, OrdenCompra.Estatus.RECIBIDA)


class MermaDeRecepcionTests(TestCase):
    """B22 (docs/AUDITORIA.md): la merma bajaba el subtotal de la orden pero
    no su IVA/IEPS, y la cuenta por pagar se quedaba con el impuesto completo."""

    @classmethod
    def setUpTestData(cls):
        cls.cedis = Almacen.objects.create(nombre="CEDIS", tipo=Almacen.Tipo.CEDIS, numero=1)
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Prueba",
            regimen_fiscal=regimen,
        )
        cls.gravado = Producto.objects.create(
            nombre="Alimento", sku="ALI", tipo_iva=Producto.TipoIVA.GRAVADO, tasa_iva=Decimal("16.00"),
        )
        cls.con_ieps = Producto.objects.create(
            nombre="Botana", sku="BOT", tipo_iva=Producto.TipoIVA.GRAVADO, tasa_iva=Decimal("16.00"),
            aplica_ieps=True, tasa_ieps=Decimal("8.00"),
        )

    def _orden_recibida(self, producto, iva, ieps=Decimal("0.00")):
        orden = OrdenCompra.objects.create(
            proveedor=self.proveedor, almacen_destino=self.cedis, fecha_orden=date(2026, 9, 1),
            estatus=OrdenCompra.Estatus.RECIBIDA, iva=iva, ieps=ieps,
        )
        detalle = OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("10.00"),
            cantidad_recibida=Decimal("10"),
        )
        lote = Lote.objects.create(
            producto=producto, almacen=self.cedis, orden_compra_detalle=detalle, fecha_ingreso=date(2026, 9, 2),
            costo_unitario=Decimal("10.00"), cantidad_inicial=10, cantidad_disponible=10,
        )
        return orden, lote

    def test_sin_capturarlo_descuenta_el_iva_que_corresponde_a_la_merma(self):
        orden, lote = self._orden_recibida(self.gravado, iva=Decimal("16.00"))
        cuenta = CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("116.00"),
            fecha_emision=date(2026, 9, 3), fecha_vencimiento=date(2026, 10, 3),
        )

        registrar_merma_recepcion(lote, Decimal("2"))

        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual(orden.iva, Decimal("12.80"))
        self.assertEqual(orden.total, Decimal("92.80"))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.monto_total, Decimal("92.80"))

    def test_el_ieps_forma_parte_de_la_base_del_iva(self):
        orden, lote = self._orden_recibida(self.con_ieps, iva=Decimal("17.28"), ieps=Decimal("8.00"))

        self.assertEqual(
            sugerir_impuestos_de_merma(lote.orden_compra_detalle, Decimal("1")), (Decimal("1.73"), Decimal("0.80")),
        )
        registrar_merma_recepcion(lote, Decimal("1"))

        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual((orden.iva, orden.ieps), (Decimal("15.55"), Decimal("7.20")))

    def test_respeta_lo_que_trae_la_nota_de_credito_y_no_pasa_de_lo_de_la_orden(self):
        orden, lote = self._orden_recibida(self.gravado, iva=Decimal("16.00"))

        with self.assertRaisesMessage(ValueError, "no puede ser mayor al de la orden"):
            registrar_merma_recepcion(lote, Decimal("2"), iva=Decimal("16.01"))
        registrar_merma_recepcion(Lote.objects.get(pk=lote.pk), Decimal("2"), iva=Decimal("3.00"))

        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).iva, Decimal("13.00"))

    def test_orden_sin_iva_no_descuenta_nada(self):
        orden, lote = self._orden_recibida(self.gravado, iva=Decimal("0.00"))
        registrar_merma_recepcion(lote, Decimal("2"))
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).total, Decimal("80.00"))

    def test_la_pantalla_propone_el_iva_y_lo_aplica(self):
        orden, lote = self._orden_recibida(self.gravado, iva=Decimal("16.00"))
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        url = reverse("inventario:lote-merma", args=[lote.pk])

        self.assertContains(self.client.get(url), "IVA a descontar")
        respuesta = self.client.post(url, {"cantidad": "2", "iva": "", "ieps": "", "motivo": ""})

        self.assertRedirects(respuesta, reverse("inventario:lote-list"), fetch_redirect_response=False)
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).iva, Decimal("12.80"))
