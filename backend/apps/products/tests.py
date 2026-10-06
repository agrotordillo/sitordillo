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
