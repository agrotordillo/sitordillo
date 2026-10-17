from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Almacen, ListaPrecio, Producto, ProductoPrecio, PuntoVenta
from apps.products.services import abrir_turno, resolver_precio_linea

User = get_user_model()


class NextSeguroTests(TestCase):
    """B12 (docs/AUDITORIA.md): después de guardar se redirigía a lo que
    trajera `next`, aunque apuntara a otro sitio."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        cls.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_activar_desactivar_no_redirige_fuera_del_sitio(self):
        url = reverse("products:product-toggle-activo", args=[self.producto.pk])

        respuesta = self.client.post(url, {"next": "https://evil.example/robo"})
        self.assertRedirects(respuesta, reverse("products:product-list"), fetch_redirect_response=False)

        respuesta = self.client.post(url, {"next": "/productos/?q=croqueta"})
        self.assertRedirects(respuesta, "/productos/?q=croqueta", fetch_redirect_response=False)

    def test_el_formulario_no_pinta_un_cancelar_hacia_otro_sitio(self):
        respuesta = self.client.get(
            reverse("products:product-update", args=[self.producto.pk]), {"next": "javascript:alert(1)"}
        )
        self.assertEqual(respuesta.context["next_url"], str(reverse("products:product-list")))
        self.assertNotContains(respuesta, "javascript:alert(1)")


class TurnoYaAbiertoTests(TestCase):
    """B27 (docs/AUDITORIA.md): abrir un turno en una caja que ya tenía uno
    mostraba el nombre técnico de la restricción de la base de datos."""

    def test_mensaje_claro(self):
        sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        caja = PuntoVenta.objects.create(almacen=sucursal, codigo="C1", numero=1, nombre="Caja 1")
        admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        otro = User.objects.create_superuser(username="otro", password="S3guridad!2026")
        abrir_turno(caja, otro)

        with self.assertRaises(ValidationError) as error:
            abrir_turno(caja, admin)
        self.assertEqual(error.exception.messages, ["Este punto de venta ya tiene un turno abierto."])

        self.client.force_login(admin)
        respuesta = self.client.post(reverse("products:turno-abrir"), {"punto_venta": caja.pk}, follow=True)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertIn("Este punto de venta ya tiene un turno abierto.", mensajes)
        self.assertFalse(any("trn_un_turno" in m for m in mensajes))


class PrecioDePaqueteTests(TestCase):
    """B25 (docs/AUDITORIA.md), decisión del usuario: un paquete se arma a
    su costo real y se vende siempre con la lista PROMOCION, sin importar la
    lista del cliente."""

    @classmethod
    def setUpTestData(cls):
        cls.sucursal = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.mayoreo = ListaPrecio.objects.get_or_create(nombre="MAYOREO")[0]
        cls.promocion = ListaPrecio.objects.get_or_create(nombre="PROMOCION")[0]
        cls.paquete = Producto.objects.create(
            nombre="Combo croqueta", sku="CMB", tipo=Producto.TipoProducto.PAQUETE, almacen=cls.sucursal,
            precio_venta=Decimal("300.00"),
        )
        cls.croqueta = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_venta=Decimal("120.00"))
        for producto, lista, precio in (
            (cls.paquete, cls.mayoreo, "280.00"),
            (cls.paquete, cls.promocion, "250.00"),
            (cls.croqueta, cls.mayoreo, "110.00"),
            (cls.croqueta, cls.promocion, "100.00"),
        ):
            ProductoPrecio.objects.create(producto=producto, lista_precio=lista, precio_con_impuesto=Decimal(precio))

    def test_el_paquete_se_cobra_con_promocion_y_lo_demas_con_la_lista_del_cliente(self):
        self.assertEqual(
            resolver_precio_linea(self.paquete, self.mayoreo, self.sucursal), (Decimal("250.00"), self.promocion),
        )
        self.assertEqual(
            resolver_precio_linea(self.croqueta, self.mayoreo, self.sucursal), (Decimal("110.00"), self.mayoreo),
        )

    def test_paquete_sin_precio_de_promocion_usa_la_lista_del_cliente(self):
        ProductoPrecio.objects.filter(producto=self.paquete, lista_precio=self.promocion).delete()
        self.assertEqual(
            resolver_precio_linea(self.paquete, self.mayoreo, self.sucursal), (Decimal("280.00"), self.mayoreo),
        )

    def test_el_buscador_ignora_una_sucursal_de_precio_invalida(self):
        # B28: antes daba error 500.
        self.client.force_login(User.objects.create_superuser(username="admin2", password="S3guridad!2026"))
        respuesta = self.client.get(reverse("api:producto-buscar"), {"q": "Combo", "precio_almacen": "abc"})
        self.assertEqual(respuesta.json()[0]["precio_venta"], "300.00")

    def test_el_buscador_de_ventas_muestra_el_precio_de_promocion(self):
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        respuesta = self.client.get(reverse("api:producto-buscar"), {"q": "Combo", "precio_almacen": self.sucursal.pk})
        self.assertEqual(respuesta.json()[0]["precio_venta"], "250.00")


class ConfirmarActualizarPreciosListaTests(TestCase):
    """Al cambiar el costo en la edición del producto se pregunta si también
    se actualizan los precios de lista (campo oculto actualizar_precios_lista,
    ver producto-costo-confirmar.js). Si sí, las listas con % de utilidad se
    recalculan y el precio de venta toma el de Público en general."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        cls.publico = ListaPrecio.objects.get_or_create(nombre="PUBLICO", defaults={"orden": 1})[0]
        cls.mayoreo = ListaPrecio.objects.get_or_create(nombre="MAYOREO", defaults={"orden": 3})[0]

    def setUp(self):
        self.client.force_login(self.admin)
        self.producto = Producto.objects.create(
            nombre="Croqueta", sku="CRQ", precio_costo=Decimal("100.0000"), precio_venta=Decimal("151.00"),
            tasa_iva=Decimal("16.00"),
        )
        # Público con 30% de utilidad: 100 × 1.30 × 1.16 = 150.80 -> 151.00.
        self.precio_publico = ProductoPrecio.objects.create(
            producto=self.producto, lista_precio=self.publico, utilidad_pct=Decimal("30"),
            precio_con_impuesto=Decimal("151.00"),
        )
        # Mayoreo capturado a mano (sin % de utilidad): nunca se recalcula.
        self.precio_mayoreo = ProductoPrecio.objects.create(
            producto=self.producto, lista_precio=self.mayoreo, precio_con_impuesto=Decimal("140.00"),
        )

    def _editar(self, **cambios):
        datos = {
            "nombre": self.producto.nombre, "sku": self.producto.sku, "tipo": "producto",
            "tipo_iva": "gravado", "tasa_iva": "16.00", "precio_costo": "100.0000", "precio_venta": "151.00",
            "stock_minimo": "0", "stock_maximo": "0",
        }
        datos.update(cambios)
        return self.client.post(reverse("products:product-update", args=[self.producto.pk]), datos)

    def test_si_actualiza_listas_con_utilidad_y_precio_de_venta_toma_publico(self):
        respuesta = self._editar(precio_costo="110.0000", precio_venta="999.00", actualizar_precios_lista="True")
        self.assertEqual(respuesta.status_code, 302)
        self.precio_publico.refresh_from_db()
        self.precio_mayoreo.refresh_from_db()
        self.producto.refresh_from_db()
        # 110 × 1.30 × 1.16 = 165.88 -> 166.00 (redondeo hacia arriba a $0.50).
        self.assertEqual(self.precio_publico.precio_con_impuesto, Decimal("166.00"))
        self.assertEqual(self.precio_mayoreo.precio_con_impuesto, Decimal("140.00"))
        self.assertEqual(self.producto.precio_costo, Decimal("110.0000"))
        self.assertEqual(self.producto.precio_venta, Decimal("166.00"))

    def test_no_guarda_solo_el_costo(self):
        respuesta = self._editar(precio_costo="110.0000", precio_venta="155.00", actualizar_precios_lista="False")
        self.assertEqual(respuesta.status_code, 302)
        self.precio_publico.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(self.precio_publico.precio_con_impuesto, Decimal("151.00"))
        self.assertEqual(self.producto.precio_costo, Decimal("110.0000"))
        self.assertEqual(self.producto.precio_venta, Decimal("155.00"))

    def test_sin_respuesta_conserva_el_recalculo_de_siempre(self):
        # Sin JavaScript el campo oculto viaja con el valor con el que se pinta.
        formulario = self.client.get(reverse("products:product-update", args=[self.producto.pk]))
        self.assertContains(formulario, 'name="actualizar_precios_lista" value="True"')
        self._editar(precio_costo="110.0000", actualizar_precios_lista="True")
        self.precio_publico.refresh_from_db()
        self.assertEqual(self.precio_publico.precio_con_impuesto, Decimal("166.00"))

    def test_el_formulario_trae_las_listas_para_la_confirmacion(self):
        respuesta = self.client.get(reverse("products:product-update", args=[self.producto.pk]))
        datos = respuesta.context["precios_con_utilidad"]
        self.assertEqual(datos["publico_general"], "151.00")
        self.assertEqual([f["lista"] for f in datos["filas"]], ["PUBLICO"])
        self.assertTrue(datos["filas"][0]["es_publico_general"])

    def test_guardar_la_pantalla_de_precios_iguala_el_precio_de_venta_a_publico(self):
        url = reverse("products:producto-precios", args=[self.producto.pk])
        respuesta = self.client.post(url, {
            "precios-TOTAL_FORMS": "2", "precios-INITIAL_FORMS": "2",
            "precios-MIN_NUM_FORMS": "0", "precios-MAX_NUM_FORMS": "1000",
            "precios-0-id": self.precio_publico.pk, "precios-0-lista_precio": self.publico.pk,
            "precios-0-almacen": "", "precios-0-utilidad_pct": "", "precios-0-precio_con_impuesto": "175.00",
            "precios-1-id": self.precio_mayoreo.pk, "precios-1-lista_precio": self.mayoreo.pk,
            "precios-1-almacen": "", "precios-1-utilidad_pct": "", "precios-1-precio_con_impuesto": "140.00",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_venta, Decimal("175.00"))


class OrdenListaPreciosTests(TestCase):
    """La pantalla de Precios de un producto siempre muestra las listas en el
    orden del sistema anterior: las 5 generales, Público Iquinuapa, Público
    Huimanguillo y luego Público y Mayoreo del CEDIS (identificado por su
    tipo, no por su nombre). Cualquier otra combinación va al final."""

    def test_orden_canonico_aunque_se_hayan_guardado_revueltas(self):
        from apps.products.forms import ProductoPrecioFormSet

        listas = {
            nombre: ListaPrecio.objects.get_or_create(nombre=nombre, defaults={"orden": orden})[0]
            for orden, nombre in enumerate(["PUBLICO", "MEDIO MAYOREO", "MAYOREO", "SUB DISTRIBUIDOR", "PROMOCION"], 1)
        }
        iquinuapa = Almacen.objects.create(nombre="IQUINUAPA", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        huimanguillo = Almacen.objects.create(nombre="HUIMANGUILLO", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        cedis = Almacen.objects.create(nombre="CEDIS BODEGA SUR", tipo=Almacen.Tipo.CEDIS, numero=3)
        bodega_sur = Almacen.objects.create(nombre="BODEGA SUR", tipo=Almacen.Tipo.SUCURSAL, numero=4)
        producto = Producto.objects.create(nombre="Sulfa", sku="3S100")

        revueltas = [
            ("MAYOREO", bodega_sur), ("MAYOREO", cedis), ("PUBLICO", bodega_sur), ("PROMOCION", None),
            ("PUBLICO", cedis), ("PUBLICO", huimanguillo), ("PUBLICO", None), ("SUB DISTRIBUIDOR", None),
            ("PUBLICO", iquinuapa), ("MAYOREO", None), ("MEDIO MAYOREO", None),
        ]
        for lista, almacen in revueltas:
            ProductoPrecio.objects.create(
                producto=producto, lista_precio=listas[lista], almacen=almacen, precio_con_impuesto=Decimal("10"),
            )

        formset = ProductoPrecioFormSet(instance=producto, prefix="precios")
        orden = [
            (f.instance.lista_precio.nombre, f.instance.almacen.nombre if f.instance.almacen_id else None)
            for f in formset.forms if f.instance.pk
        ]
        self.assertEqual(orden, [
            ("PUBLICO", None), ("MEDIO MAYOREO", None), ("MAYOREO", None), ("SUB DISTRIBUIDOR", None),
            ("PROMOCION", None), ("PUBLICO", "IQUINUAPA"), ("PUBLICO", "HUIMANGUILLO"),
            ("PUBLICO", "CEDIS BODEGA SUR"), ("MAYOREO", "CEDIS BODEGA SUR"),
            # Fuera de la tabla del sistema anterior: al final.
            ("PUBLICO", "BODEGA SUR"), ("MAYOREO", "BODEGA SUR"),
        ])


class UnidadAuxiliarTests(TestCase):
    """Unidad auxiliar del sistema anterior: el contenido de cada presentación
    (1 PIEZA = 100 ML), con el que el negocio identifica el producto."""

    @classmethod
    def setUpTestData(cls):
        from apps.products.models import UnidadMedida

        cls.pieza = UnidadMedida.objects.create(nombre="PIEZA", abreviatura="PZA")
        cls.ml = UnidadMedida.objects.create(nombre="MILILITRO", abreviatura="ML")
        cls.kg = UnidadMedida.objects.create(nombre="KILOGRAMO", abreviatura="KG")

    def test_reglas_de_importacion(self):
        from apps.products.management.commands.import_legacy_productos import campos_unidad_auxiliar

        unidades = {1: self.pieza, 2: self.ml}
        fila = {"id_unidad_medida_auxiliar": 2, "factor_unidad_medida_auxiliar": "100.00000000", "control_auxiliar": "NO"}
        campos, sin_unidad = campos_unidad_auxiliar(fila, unidades)
        self.assertEqual(campos, {"unidad_medida_auxiliar": self.ml, "factor_unidad_auxiliar": Decimal("100.0000"), "control_auxiliar": False})
        self.assertFalse(sin_unidad)

        # Factor 0 en el legado = sin capturar: no se trae la unidad suelta.
        fila = {"id_unidad_medida_auxiliar": 1, "factor_unidad_medida_auxiliar": "0.00000000", "control_auxiliar": "SI"}
        campos, sin_unidad = campos_unidad_auxiliar(fila, unidades)
        self.assertEqual(campos, {"unidad_medida_auxiliar": None, "factor_unidad_auxiliar": None, "control_auxiliar": True})
        self.assertFalse(sin_unidad)

        # Factor sin unidad: no se trae y se reporta.
        fila = {"id_unidad_medida_auxiliar": None, "factor_unidad_medida_auxiliar": "40.00000000", "control_auxiliar": ""}
        campos, sin_unidad = campos_unidad_auxiliar(fila, unidades)
        self.assertIsNone(campos["factor_unidad_auxiliar"])
        self.assertTrue(sin_unidad)

    def test_contenido_display(self):
        producto = Producto(nombre="Sulfa", sku="3S100", unidad_medida_auxiliar=self.ml, factor_unidad_auxiliar=Decimal("100.0000"))
        self.assertEqual(producto.contenido_display, "100 ML")
        producto.unidad_medida_auxiliar, producto.factor_unidad_auxiliar = self.kg, Decimal("0.5000")
        self.assertEqual(producto.contenido_display, "0.5 KG")
        self.assertEqual(Producto(nombre="Sin", sku="X").contenido_display, "")

    def test_formulario_pide_unidad_y_factor_juntos(self):
        admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        self.client.force_login(admin)
        producto = Producto.objects.create(nombre="Sulfa", sku="3S100")
        url = reverse("products:product-update", args=[producto.pk])
        base = {
            "nombre": "Sulfa", "sku": "3S100", "tipo": "producto", "tipo_iva": "gravado", "tasa_iva": "16.00",
            "precio_costo": "0", "precio_venta": "0", "stock_minimo": "0", "stock_maximo": "0",
            "actualizar_precios_lista": "False",
        }

        respuesta = self.client.post(url, {**base, "factor_unidad_auxiliar": "100"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("unidad_medida_auxiliar", respuesta.context["form"].errors)

        respuesta = self.client.post(url, {**base, "unidad_medida_auxiliar": self.ml.pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("factor_unidad_auxiliar", respuesta.context["form"].errors)

        respuesta = self.client.post(url, {**base, "unidad_medida_auxiliar": self.ml.pk, "factor_unidad_auxiliar": "100"})
        self.assertEqual(respuesta.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.contenido_display, "100 ML")


class ListadoPersonalizableTests(TestCase):
    """"Columnas" y "Agrupar por" del listado de Productos, como en el
    sistema anterior: cada usuario elige qué columnas ver, en qué orden, y
    si se agrupa (estático: un campo; dinámico: varios niveles). Se guarda
    por usuario y lo respeta también el Excel."""

    @classmethod
    def setUpTestData(cls):
        from apps.products.models import Linea, Marca

        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")
        cls.otro = User.objects.create_superuser(username="otro", password="S3guridad!2026")
        cls.perros = Linea.objects.create(nombre="PERROS")
        cls.gatos = Linea.objects.create(nombre="GATOS")
        cls.marca = Marca.objects.create(nombre="NUPEC")
        publico = ListaPrecio.objects.get_or_create(nombre="PUBLICO", defaults={"orden": 1})[0]
        iquinuapa = Almacen.objects.create(nombre="IQUINUAPA", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        # 30 de PERROS (más de una página), 1 de GATOS y 1 sin línea.
        for numero in range(30):
            Producto.objects.create(nombre=f"Croqueta {numero:02d}", sku=f"CRQ{numero:02d}", linea=cls.perros, marca=cls.marca)
        cls.arena = Producto.objects.create(nombre="Arena", sku="ARN", linea=cls.gatos)
        Producto.objects.create(nombre="Collar", sku="COL")
        ProductoPrecio.objects.create(
            producto=cls.arena, lista_precio=publico, almacen=iquinuapa, precio_con_impuesto=Decimal("88.50"),
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("products:product-list")
        self.url_preferencias = reverse("products:product-list-preferencias")

    def titulos(self, respuesta):
        return [columna.titulo for columna in respuesta.context["columnas"]]

    def test_columnas_por_defecto(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(
            self.titulos(respuesta),
            ["Código", "Nombre", "Tipo", "Unidad", "Estado", "Costo",
             "Público", "Medio mayoreo", "Mayoreo", "Sub distribuidor", "Promoción"],
        )

    def test_elegir_columnas_y_orden_por_usuario(self):
        respuesta = self.client.post(self.url_preferencias, {
            "accion": "columnas", "columnas": ["nombre", "precio_6", "linea", "no_existe", "nombre"],
            "next": "/productos/?q=arena",
        })
        self.assertRedirects(respuesta, "/productos/?q=arena", fetch_redirect_response=False)

        respuesta = self.client.get(self.url, {"q": "arena"})
        # Costo es fija: si no se manda, se agrega igual.
        self.assertEqual(self.titulos(respuesta), ["Nombre", "Público Iquinuapa", "Línea", "Costo"])
        self.assertContains(respuesta, "88.50")
        self.assertContains(respuesta, "GATOS")

        # El otro usuario sigue con las columnas por defecto.
        self.client.force_login(self.otro)
        self.assertEqual(self.titulos(self.client.get(self.url))[0], "Código")

        self.client.force_login(self.admin)
        self.client.post(self.url_preferencias, {"accion": "restablecer_columnas"})
        self.assertEqual(self.titulos(self.client.get(self.url))[0], "Código")

    def test_agrupar_estatico_cuenta_todo_el_resultado(self):
        self.client.post(self.url_preferencias, {"accion": "agrupar", "modo": "estatico", "agrupar_estatico": "linea"})
        respuesta = self.client.get(self.url)
        grupos = [fila for fila in respuesta.context["filas"] if fila["es_grupo"]]
        # Página 1 (25 productos): GATOS primero, luego PERROS con sus 30 aunque
        # en esta página solo se vean 24.
        self.assertEqual([(g["valor"], g["conteo"]) for g in grupos], [("GATOS", 1), ("PERROS", 30)])

        respuesta = self.client.get(self.url, {"page": 2})
        grupos = [(f["valor"], f["conteo"]) for f in respuesta.context["filas"] if f["es_grupo"]]
        self.assertEqual(grupos, [("PERROS", 30), ("Sin línea", 1)])

        # Un valor que no está en la lista de estáticos no agrupa.
        self.client.post(self.url_preferencias, {"accion": "agrupar", "modo": "estatico", "agrupar_estatico": "tipo"})
        self.assertEqual(self.client.get(self.url).context["agrupar"], [])

    def test_agrupar_dinamico_anida_niveles(self):
        self.client.post(self.url_preferencias, {
            "accion": "agrupar", "modo": "dinamico", "agrupar": ["linea", "marca", "inventado"],
        })
        respuesta = self.client.get(self.url, {"q": "croqueta 0"})
        filas = respuesta.context["filas"]
        self.assertEqual([a.clave for a in respuesta.context["agrupar"]], ["linea", "marca"])
        linea, marca = filas[0], filas[1]
        self.assertEqual((linea["valor"], linea["nivel"], linea["conteo"]), ("PERROS", 0, 10))
        self.assertEqual((marca["valor"], marca["nivel"], marca["grupos"]), ("NUPEC", 1, linea["id"]))
        self.assertEqual(filas[2]["grupos"], f'{linea["id"]} {marca["id"]}')

    def test_excel_respeta_columnas_y_grupos(self):
        import io

        import openpyxl

        self.client.post(self.url_preferencias, {"accion": "columnas", "columnas": ["sku", "nombre"]})
        self.client.post(self.url_preferencias, {"accion": "agrupar", "modo": "estatico", "agrupar_estatico": "linea"})
        respuesta = self.client.get(reverse("products:product-exportar"), {"q": "a"})
        hoja = openpyxl.load_workbook(io.BytesIO(respuesta.content)).active
        filas = [tuple(celda.value for celda in fila) for fila in hoja.iter_rows()]
        self.assertEqual(filas[0], ("Código", "Nombre", "Costo"))
        self.assertEqual(filas[1][0], "Línea: GATOS (1)")
        self.assertEqual(filas[2], ("ARN", "Arena", 0.0))
        self.assertEqual(filas[3][0], "Línea: PERROS (30)")
