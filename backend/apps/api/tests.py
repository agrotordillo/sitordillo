from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.products.models import ListaPrecio, Marca, Producto, ProductoPrecio

User = get_user_model()


class PermisosApiProductosTests(TestCase):
    """B08 (docs/AUDITORIA.md): cualquier usuario con sesión cambiaba el
    costo de un producto -y con él sus precios de lista- y daba de alta
    catálogos desde la API."""

    @classmethod
    def setUpTestData(cls):
        cls.producto = Producto.objects.create(nombre="Croqueta", sku="CRQ", precio_costo=Decimal("100.0000"))
        cls.mostrador = cls._usuario("mostrador", "Mostrador y Cotización")
        cls.captura = cls._usuario("captura", "Compras - Captura")
        cls.compras = cls._usuario("compras", "Compras - Completo")

    @staticmethod
    def _usuario(username, grupo):
        usuario = User.objects.create_user(username=username, password="S3guridad!2026")
        usuario.groups.add(Group.objects.get(name=grupo))
        return usuario

    def _actualizar_costo(self, usuario, precio_costo):
        self.client.force_login(usuario)
        return self.client.post(
            reverse("api:producto-actualizar-costo"),
            {"producto": self.producto.pk, "precio_costo": precio_costo},
            content_type="application/json",
        )

    def test_solo_quien_edita_productos_actualiza_el_costo(self):
        self.assertEqual(self._actualizar_costo(self.mostrador, "1.00").status_code, 403)
        self.assertEqual(self._actualizar_costo(self.captura, "1.00").status_code, 403)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_costo, Decimal("100.0000"))

        respuesta = self._actualizar_costo(self.compras, "120.50")
        self.assertEqual(respuesta.status_code, 200)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_costo, Decimal("120.5000"))

    def test_actualizar_el_costo_recalcula_los_precios_con_utilidad(self):
        lista = ListaPrecio.objects.get_or_create(nombre="PUBLICO")[0]
        precio = ProductoPrecio.objects.create(
            producto=self.producto, lista_precio=lista, utilidad_pct=Decimal("50"), precio_con_impuesto=Decimal("174.00"),
        )
        self._actualizar_costo(self.compras, "200")
        precio.refresh_from_db()
        self.assertEqual(precio.precio_con_impuesto, Decimal("348.00"))

    def test_rechaza_valores_invalidos_con_400(self):
        for invalido in ("abc", "NaN", "Infinity", "-1", "1.12345", ""):
            self.assertEqual(self._actualizar_costo(self.compras, invalido).status_code, 400, invalido)

    def test_altas_rapidas_solo_para_quien_crea_o_edita_productos(self):
        url = reverse("api:brand-quick-create")

        self.client.force_login(self.mostrador)
        self.assertEqual(self.client.post(url, {"nombre": "Marca nueva"}).status_code, 403)
        self.assertFalse(Marca.objects.filter(nombre="Marca nueva").exists())

        self.client.force_login(self.compras)
        self.assertEqual(self.client.post(url, {"nombre": "Marca nueva"}).status_code, 201)
        self.assertTrue(Marca.objects.filter(nombre="Marca nueva").exists())

    def test_la_orden_de_compra_solo_muestra_el_boton_a_quien_puede_usarlo(self):
        url_costo = reverse("api:producto-actualizar-costo")

        self.client.force_login(self.captura)
        self.assertNotContains(self.client.get(reverse("compras:orden-create")), url_costo)

        self.client.force_login(self.compras)
        self.assertContains(self.client.get(reverse("compras:orden-create")), url_costo)
