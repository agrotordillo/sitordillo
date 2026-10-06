import importlib
from datetime import date
from decimal import Decimal
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.compras.forms import OrdenCompraDetalleFormSet, OrdenCompraForm
from apps.compras.models import OrdenCompra, OrdenCompraDetalle
from apps.fiscal.models import RegimenFiscal
from apps.pagos.models import CuentaPorPagar
from apps.products.models import Almacen, Producto
from apps.proveedores.models import Proveedor

User = get_user_model()


class DescuentoBaseProveedorTests(TestCase):
    """B01/B02 (docs/AUDITORIA.md): el % base del proveedor se leía en vivo
    -editar el proveedor reescribía órdenes ya capturadas- y en una orden
    cargada desde CFDI se restaba aunque su precio ya venía neto."""

    @classmethod
    def setUpTestData(cls):
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor 10",
            regimen_fiscal=regimen, descuento=Decimal("10.00"),
        )
        cls.otro_proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="BBB010101BBB", nombre_fiscal="Proveedor 5",
            regimen_fiscal=regimen, descuento=Decimal("5.00"),
        )
        cls.producto = Producto.objects.create(nombre="Alimento", sku="ALI")

    def _orden(self, proveedor=None, precio=Decimal("100.00"), **extra):
        orden = OrdenCompra.objects.create(proveedor=proveedor or self.proveedor, fecha_orden=date(2026, 9, 1), **extra)
        OrdenCompraDetalle.objects.create(orden_compra=orden, producto=self.producto, cantidad=1, precio_unitario=precio)
        return OrdenCompra.objects.get(pk=orden.pk)

    def test_la_orden_congela_el_descuento_vigente_al_registrarse(self):
        orden = self._orden()
        self.assertEqual(orden.descuento_base_pct, Decimal("10.00"))
        self.assertEqual(orden.total, Decimal("90.00"))
        self.assertEqual(orden.detalles.get().precio_neto, Decimal("90.00"))

    def test_editar_el_descuento_del_proveedor_no_cambia_ordenes_ya_capturadas(self):
        orden = self._orden()
        Proveedor.objects.filter(pk=self.proveedor.pk).update(descuento=Decimal("20.00"))

        orden = OrdenCompra.objects.get(pk=orden.pk)
        orden.observaciones = "Editada después"
        orden.save()

        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual(orden.descuento_base_pct, Decimal("10.00"))
        self.assertEqual(orden.total, Decimal("90.00"))

    def test_cambiar_el_proveedor_de_la_orden_toma_el_descuento_del_nuevo(self):
        orden = self._orden()
        orden.proveedor = self.otro_proveedor
        orden.save()
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).descuento_base_pct, Decimal("5.00"))

    def test_orden_de_cfdi_no_resta_el_descuento_base(self):
        orden = self._orden(precio=Decimal("90.00"), cfdi_uuid="UUID-CFDI-1")
        self.assertEqual(orden.descuento_base_pct, Decimal("0.00"))
        self.assertEqual(orden.total, Decimal("90.00"))
        self.assertEqual(orden.detalles.get().precio_neto, Decimal("90.00"))

    def test_el_adicional_de_la_orden_se_suma_al_base_congelado(self):
        orden = self._orden(descuento_pct=Decimal("5.00"))
        self.assertEqual(orden.descuento_pct_total, Decimal("15.00"))
        self.assertEqual(orden.total, Decimal("85.00"))

    def test_el_formulario_usa_el_mismo_descuento_base_que_el_total(self):
        orden = self._orden()
        Proveedor.objects.filter(pk=self.proveedor.pk).update(descuento=Decimal("20.00"))
        orden = OrdenCompra.objects.get(pk=orden.pk)

        def data_descuento(form):
            return form.fields["proveedor"].widget.attrs.get("data-descuento")

        self.assertEqual(data_descuento(OrdenCompraForm(instance=orden)), "10.00")
        cambiado = OrdenCompraForm(data={"proveedor": self.otro_proveedor.pk}, instance=orden)
        self.assertEqual(data_descuento(cambiado), "5.00")
        self.assertEqual(data_descuento(OrdenCompraForm(data={"proveedor": self.proveedor.pk})), "20.00")
        self.assertIsNone(data_descuento(OrdenCompraForm()))

        cfdi = self._orden(cfdi_uuid="UUID-CFDI-2")
        form_cfdi = OrdenCompraForm(instance=cfdi)
        self.assertEqual(data_descuento(form_cfdi), "0.00")
        self.assertEqual(form_cfdi.fields["proveedor"].widget.attrs.get("data-sin-descuento-base"), "true")

    def test_las_pantallas_de_la_orden_cargan_con_el_descuento_congelado(self):
        orden = self._orden()
        Proveedor.objects.filter(pk=self.proveedor.pk).update(descuento=Decimal("20.00"))
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))

        self.assertEqual(self.client.get(reverse("compras:orden-create")).status_code, 200)
        editar = self.client.get(reverse("compras:orden-update", args=[orden.pk]))
        self.assertContains(editar, 'data-descuento="10.00"')

    def test_la_migracion_congela_el_descuento_actual_salvo_en_ordenes_de_cfdi(self):
        normal = self._orden()
        cfdi = self._orden(cfdi_uuid="UUID-CFDI-3")
        OrdenCompra.objects.update(descuento_base_pct=Decimal("0.00"))

        migracion = importlib.import_module("apps.compras.migrations.0012_ordencompra_descuento_base_pct")
        migracion.congelar_descuento_base(django_apps, None)

        self.assertEqual(OrdenCompra.objects.get(pk=normal.pk).descuento_base_pct, Decimal("10.00"))
        self.assertEqual(OrdenCompra.objects.get(pk=cfdi.pk).descuento_base_pct, Decimal("0.00"))


class AnalisisDeCompraTests(TestCase):
    """B30 (docs/AUDITORIA.md): el análisis de compra por producto contaba
    órdenes canceladas, a diferencia del análisis anual."""

    def test_solo_cuenta_compras_reales(self):
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Uno",
            regimen_fiscal=regimen,
        )
        producto = Producto.objects.create(nombre="Alimento", sku="ALI")
        for estatus in OrdenCompra.Estatus:
            orden = OrdenCompra.objects.create(proveedor=proveedor, fecha_orden=date(2026, 9, 1), estatus=estatus)
            OrdenCompraDetalle.objects.create(
                orden_compra=orden, producto=producto, cantidad=1, precio_unitario=Decimal("10.00"),
            )
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))

        respuesta = self.client.get(reverse("compras:analisis-producto"))

        mostradas = {d.orden_compra.estatus for d in respuesta.context["detalles"]}
        self.assertEqual(
            mostradas,
            {OrdenCompra.Estatus.ENVIADA, OrdenCompra.Estatus.PARCIAL, OrdenCompra.Estatus.RECIBIDA},
        )


class OrdenConRecepcionesTests(TestCase):
    """B20 (docs/AUDITORIA.md): una orden ya recibida se podía regresar a
    Borrador o cancelar, y se le podían borrar, cambiar o bajar líneas con
    mercancía en inventario. Decisión: solo se editan precios y datos de la
    factura; "Parcial" y "Recibida" los pone el sistema."""

    @classmethod
    def setUpTestData(cls):
        regimen = RegimenFiscal.objects.get_or_create(
            clave="601", defaults={"descripcion": "General de Ley Personas Morales", "aplica_moral": True}
        )[0]
        cls.proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="AAA010101AAA", nombre_fiscal="Proveedor Uno",
            regimen_fiscal=regimen,
        )
        cls.otro_proveedor = Proveedor.objects.create(
            tipo_persona=Proveedor.TipoPersona.MORAL, rfc="BBB010101BBB", nombre_fiscal="Proveedor Dos",
            regimen_fiscal=regimen,
        )
        cls.cedis = Almacen.objects.create(nombre="CEDIS", tipo=Almacen.Tipo.CEDIS, numero=1)
        cls.producto = Producto.objects.create(nombre="Alimento", sku="ALI")
        cls.otro_producto = Producto.objects.create(nombre="Otro alimento", sku="OTR")
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

    def setUp(self):
        self.client.force_login(self.admin)

    def _orden(self, estatus=OrdenCompra.Estatus.RECIBIDA, recibida=Decimal("10")):
        orden = OrdenCompra.objects.create(
            proveedor=self.proveedor, almacen_destino=self.cedis, fecha_orden=date(2026, 9, 1), estatus=estatus,
        )
        detalle = OrdenCompraDetalle.objects.create(
            orden_compra=orden, producto=self.producto, cantidad=Decimal("10"),
            precio_unitario=Decimal("10.00"), cantidad_recibida=recibida,
        )
        return OrdenCompra.objects.get(pk=orden.pk), detalle

    def _post(self, orden, filas, **cambios):
        """Envía la orden como la mostraría la pantalla, con `cambios` en el
        encabezado y `filas` como líneas del formset."""
        form = OrdenCompraForm(instance=orden)
        datos = {}
        for nombre in form.fields:
            valor = form[nombre].value()
            if nombre == "documento" or valor is None or valor is False or valor == "":
                continue
            datos[nombre] = "on" if valor is True else valor
        datos.update(cambios)
        datos.update({
            "detalles-TOTAL_FORMS": len(filas),
            "detalles-INITIAL_FORMS": sum(1 for fila in filas if "id" in fila),
            "detalles-MIN_NUM_FORMS": 0,
            "detalles-MAX_NUM_FORMS": 1000,
        })
        for i, fila in enumerate(filas):
            for campo, valor in fila.items():
                datos[f"detalles-{i}-{campo}"] = valor
        return self.client.post(reverse("compras:orden-update", args=[orden.pk]), datos)

    def _assertGuardo(self, respuesta):
        errores = respuesta.context and (
            respuesta.context["form"].errors, respuesta.context["formset"].errors,
            respuesta.context["formset"].non_form_errors(),
        )
        self.assertEqual(respuesta.status_code, 302, errores)

    def _fila(self, detalle, **cambios):
        return {
            "id": detalle.pk, "producto": detalle.producto_id, "cantidad": detalle.cantidad,
            "precio_unitario": detalle.precio_unitario, **cambios,
        }

    def _estatus_ofrecidos(self, form):
        return [valor for valor, _ in form.fields["estatus"].choices]

    def test_parcial_y_recibida_no_se_eligen_a_mano(self):
        self.assertEqual(self._estatus_ofrecidos(OrdenCompraForm()), ["borrador", "enviada"])
        orden, _ = self._orden(estatus=OrdenCompra.Estatus.ENVIADA, recibida=Decimal("0"))
        self.assertEqual(self._estatus_ofrecidos(OrdenCompraForm(instance=orden)), ["borrador", "enviada", "cancelada"])

        respuesta = self._post(orden, [], estatus="recibida")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("estatus", respuesta.context["form"].errors)
        self.assertEqual(OrdenCompra.objects.get(pk=orden.pk).estatus, OrdenCompra.Estatus.ENVIADA)

    def test_no_se_cancela_una_orden_con_cuenta_por_pagar(self):
        orden, _ = self._orden(estatus=OrdenCompra.Estatus.ENVIADA, recibida=Decimal("0"))
        CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("100.00"),
            fecha_emision=date(2026, 9, 3), fecha_vencimiento=date(2026, 10, 3),
        )
        respuesta = self._post(orden, [], estatus="cancelada")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("cuenta por pagar", str(respuesta.context["form"].errors["estatus"]))

    def test_con_mercancia_recibida_estatus_proveedor_y_almacen_quedan_fijos(self):
        orden, detalle = self._orden()
        otro_almacen = Almacen.objects.create(nombre="Sucursal", tipo=Almacen.Tipo.SUCURSAL, numero=2)

        respuesta = self._post(
            orden, [self._fila(detalle, precio_unitario="11.00")],
            estatus="borrador", proveedor=self.otro_proveedor.pk, almacen_destino=otro_almacen.pk, iva="16.00",
        )

        self._assertGuardo(respuesta)
        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual(
            (orden.estatus, orden.proveedor, orden.almacen_destino),
            (OrdenCompra.Estatus.RECIBIDA, self.proveedor, self.cedis),
        )
        # Lo que sí se edita: precio y datos de la factura.
        self.assertEqual((orden.iva, orden.detalles.get().precio_unitario), (Decimal("16.00"), Decimal("11.00")))

    def test_una_linea_recibida_no_cambia_de_producto_no_se_quita_ni_baja_de_lo_recibido(self):
        orden, detalle = self._orden(recibida=Decimal("6"), estatus=OrdenCompra.Estatus.PARCIAL)

        respuesta = self._post(orden, [self._fila(detalle, cantidad="5")])
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("menor a lo ya recibido", str(respuesta.context["formset"].forms[0].errors["cantidad"]))

        respuesta = self._post(orden, [self._fila(detalle, DELETE="on")])
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("No se puede quitar", str(respuesta.context["formset"].non_form_errors()))
        # Solo el de la fila en blanco que agrega líneas nuevas.
        self.assertContains(respuesta, 'title="Quitar línea"', count=1)

        respuesta = self._post(orden, [self._fila(detalle, producto=self.otro_producto.pk)])
        self._assertGuardo(respuesta)
        detalle.refresh_from_db()
        self.assertEqual((detalle.producto, detalle.cantidad), (self.producto, Decimal("10")))

    def test_subir_lo_pedido_de_una_orden_recibida_la_regresa_a_parcial(self):
        orden, detalle = self._orden()

        respuesta = self._post(orden, [self._fila(detalle, cantidad="12")])

        self._assertGuardo(respuesta)
        orden = OrdenCompra.objects.get(pk=orden.pk)
        self.assertEqual(orden.estatus, OrdenCompra.Estatus.PARCIAL)
        self.assertEqual(orden.detalles.get().cantidad, Decimal("12"))

    def test_si_entra_una_recepcion_mientras_se_edita_no_se_guarda_nada(self):
        orden, detalle = self._orden(estatus=OrdenCompra.Estatus.ENVIADA, recibida=Decimal("0"))
        validar = OrdenCompraDetalleFormSet.is_valid

        def validar_y_recibir_a_la_vez(formset):
            resultado = validar(formset)
            OrdenCompraDetalle.objects.filter(pk=detalle.pk).update(cantidad_recibida=Decimal("4"))
            return resultado

        with mock.patch.object(OrdenCompraDetalleFormSet, "is_valid", validar_y_recibir_a_la_vez):
            respuesta = self._post(orden, [self._fila(detalle, DELETE="on")])

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Se registró una recepción", " ".join(str(m) for m in respuesta.context["messages"]))
        self.assertTrue(OrdenCompraDetalle.objects.filter(pk=detalle.pk).exists())

    def test_la_pantalla_de_una_orden_recibida_carga(self):
        orden, _ = self._orden()
        respuesta = self.client.get(reverse("compras:orden-update", args=[orden.pk]))
        self.assertContains(respuesta, "el estatus lo actualiza la recepción")
        self.assertContains(respuesta, "readonly")
