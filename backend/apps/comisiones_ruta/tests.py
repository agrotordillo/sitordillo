import shutil
import tempfile
from datetime import datetime
from decimal import Decimal
from io import StringIO

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.comisiones_ruta.models import ComisionColaboradorLinea
from apps.products.models import Almacen, Categoria, Clase, Linea, ListaPrecio, Producto
from apps.ventas.models import Venta, VentaDetalle

User = get_user_model()


class ImportComisionesP36Tests(TestCase):
    """Carga de los % por colaborador y línea desde el Excel de comisiones
    (import_comisiones_p36): la línea sale de los productos del bloque, no de
    su título, y lo que no es una línea se deja fuera."""

    @classmethod
    def setUpTestData(cls):
        cls.alimentos = Linea.objects.create(nombre="ALIMENTOS")
        cls.bombas = Linea.objects.create(nombre="REFACCIONES PARA BOMBAS")
        cls.semillas = Linea.objects.create(nombre="SEMILLAS Y FERTILIZANTES")
        Producto.objects.create(nombre="CROQUETA 20KG", sku="CRQ", linea=cls.alimentos)
        Producto.objects.create(nombre="SELLO MECANICO", sku="SEL", linea=cls.bombas)
        Producto.objects.create(nombre="TRIPLE 17 POR KG", sku="T17", linea=cls.semillas)
        cls.guillermo = User.objects.create(username="guillermo", is_active=False)

    def setUp(self):
        directorio = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directorio)
        self.archivo = f"{directorio}/p36.xlsx"
        libro = openpyxl.Workbook()
        hoja = libro.active
        hoja.title = "GUILLERMO"
        hoja.append(["BS", "GUILLERMO VALENZUELA"])
        fila = 2
        # (título, producto, % de Precio 1-2): el tercero es un bloque de
        # semillas que quedó con el título del anterior, como en el Excel real.
        for titulo, producto, pct in [
            ("ALIMENTOS", "CROQUETA 20KG", 3),
            ("REFACCIONES PARA BOMBAS", "SELLO MECANICO", 10),
            ("REFACCIONES PARA BOMBAS", "TRIPLE 17 POR KG", 5),
            ("SOBRES", "CROQUETA 20KG", 10),
        ]:
            hoja.cell(fila, 2, titulo)
            hoja.cell(fila + 1, 2, "Registros")
            hoja.cell(fila + 2, 1, producto)
            hoja.cell(fila + 3, 1, "Total")
            hoja.cell(fila + 5, 5, f"=+E{fila + 4}*{pct}%")
            hoja.cell(fila + 5, 7, f"=+G{fila + 4}*1%")
            fila += 7
        libro.save(self.archivo)

    def test_carga_por_linea_segun_los_productos_del_bloque(self):
        salida = StringIO()
        call_command("import_comisiones_p36", archivo=self.archivo, stdout=salida)

        cargados = dict(
            ComisionColaboradorLinea.objects.filter(colaborador=self.guillermo).values_list("linea__nombre", "porcentaje")
        )
        self.assertEqual(cargados, {
            "ALIMENTOS": Decimal("3.00"),
            "REFACCIONES PARA BOMBAS": Decimal("10.00"),
            "SEMILLAS Y FERTILIZANTES": Decimal("5.00"),
        })
        self.assertIn("trae productos de SEMILLAS Y FERTILIZANTES", salida.getvalue())
        # Sin la categoría SOBRES en el catálogo, el bloque no se puede cargar.
        self.assertIn("'SOBRES' no es línea, categoría ni grupo conocido", salida.getvalue())

    def test_dry_run_no_guarda(self):
        call_command("import_comisiones_p36", archivo=self.archivo, dry_run=True, stdout=StringIO())

        self.assertFalse(ComisionColaboradorLinea.objects.exists())

    def test_hojas_de_total_categorias_y_farmacia_responsiva_de_la_sucursal(self):
        Categoria.objects.create(nombre="SOBRES")
        medicos = Clase.objects.create(nombre="MEDICOS")
        lerdo = Almacen.objects.create(nombre="LERDO", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        jhony = User.objects.create(username="jhony", is_active=False)
        alberto = User.objects.create(username="alberto", is_active=False)
        with open(self.archivo, "rb") as archivo:
            libro = openpyxl.load_workbook(archivo)
        total = libro.create_sheet("JHONY")
        total["B20"], total["D20"] = "TOTAL A PERCIBIR", "=+D16*1%"
        mvz = libro.create_sheet("MVZ ALBERTO")
        mvz["C3"], mvz["C4"], mvz["F7"], mvz["H7"] = "FARMACIA RESPONSIVA", "Registros", "=+F6*4%", "=+H6*1%"
        libro.save(self.archivo)

        call_command("import_comisiones_p36", archivo=self.archivo, stdout=StringIO())

        regla = ComisionColaboradorLinea.objects.get(colaborador=jhony)
        self.assertEqual((regla.linea, regla.porcentaje, regla.porcentaje_otras_listas), (None, 1, 1))
        regla = ComisionColaboradorLinea.objects.get(colaborador=alberto)
        self.assertEqual((regla.clase, regla.almacen, regla.porcentaje), (medicos, lerdo, 4))
        # El bloque SOBRES de GUILLERMO ahora es una regla de categoría.
        self.assertTrue(ComisionColaboradorLinea.objects.filter(
            colaborador=self.guillermo, categoria__nombre="SOBRES", porcentaje=10,
        ).exists())


def _en(dia):
    return timezone.make_aware(datetime(2026, 9, dia, 12, 0))


class ReporteComisionesRutaTests(TestCase):
    """Reporte de comisión por colaborador con reglas por línea, categoría,
    clase y sobre la venta de una sucursal (ComisionColaboradorLinea)."""

    @classmethod
    def setUpTestData(cls):
        cls.lerdo = Almacen.objects.create(nombre="LERDO", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.publico = ListaPrecio.objects.get_or_create(nombre="PUBLICO")[0]
        cls.mayoreo = ListaPrecio.objects.get_or_create(nombre="MAYOREO")[0]
        cls.cliente = Cliente.objects.create(nombre="Cliente")
        farmacia = Linea.objects.create(nombre="FARMACIA")
        alimentos = Linea.objects.create(nombre="ALIMENTOS")
        sobres = Categoria.objects.create(nombre="SOBRES")
        medicos = Clase.objects.create(nombre="MEDICOS")
        sin_iva = {"tipo_iva": Producto.TipoIVA.GRAVADO, "tasa_iva": Decimal("0.00")}
        cls.antibiotico = Producto.objects.create(nombre="Antibiótico", sku="ANT", linea=farmacia, clase=medicos, **sin_iva)
        cls.sobre = Producto.objects.create(nombre="Sobre", sku="SOB", linea=farmacia, categoria=sobres, **sin_iva)
        cls.croqueta = Producto.objects.create(nombre="Croqueta", sku="CRQ", linea=alimentos, **sin_iva)
        cls.luis = User.objects.create(username="luisg", first_name="LUIS", is_active=False)
        cls.alberto = User.objects.create(username="alberto", first_name="ALBERTO", is_active=False)
        cls.marlit = User.objects.create(username="mgonzalez", first_name="MARLIT", is_active=False)
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

        regla = ComisionColaboradorLinea.objects.create
        regla(colaborador=cls.luis, linea=farmacia, porcentaje=5)
        regla(colaborador=cls.luis, categoria=sobres, porcentaje=10)
        regla(colaborador=cls.alberto, almacen=cls.lerdo, clase=medicos, porcentaje=4)
        regla(colaborador=cls.marlit, linea=alimentos, porcentaje=1, porcentaje_otras_listas=0)

        def venta(vendedor, producto, importe, lista):
            v = Venta.objects.create(cliente=cls.cliente, almacen=cls.lerdo, fecha_venta=_en(2), created_by=vendedor)
            VentaDetalle.objects.create(venta=v, producto=producto, cantidad=1, precio_unitario=importe, lista_precio=lista)

        venta(cls.luis, cls.antibiotico, Decimal("1000.00"), cls.publico)
        venta(cls.luis, cls.sobre, Decimal("200.00"), cls.publico)
        venta(cls.marlit, cls.croqueta, Decimal("500.00"), cls.publico)
        venta(cls.marlit, cls.croqueta, Decimal("800.00"), cls.mayoreo)

    def setUp(self):
        self.client.force_login(self.admin)

    def _comisiones(self, **filtros):
        respuesta = self.client.get(
            reverse("comisiones_ruta:reporte"), {"fecha_desde": "2026-09-01", "fecha_hasta": "2026-09-30", **filtros}
        )
        self.assertEqual(respuesta.status_code, 200)
        return {g["empleado"].username: g["total_comision"] for g in respuesta.context["grupos"]}, respuesta

    def test_cada_colaborador_cobra_segun_su_regla_mas_especifica(self):
        comisiones, _ = self._comisiones()

        self.assertEqual(comisiones, {
            # FARMACIA 5% sobre el antibiótico + SOBRES 10% (más específica) sobre el sobre.
            "luisg": Decimal("70.00"),
            # 4% del antibiótico de clase MEDICOS que vendió otro en LERDO.
            "alberto": Decimal("40.00"),
            # 1% de la croqueta en PUBLICO; la de MAYOREO va al 0%.
            "mgonzalez": Decimal("5.00"),
        })

    def test_el_detalle_por_venta_solo_sale_al_filtrar_un_colaborador(self):
        _, respuesta = self._comisiones()
        self.assertTrue(all(not g["filas"] for g in respuesta.context["grupos"]))

        _, respuesta = self._comisiones(empleado=self.luis.pk)
        [grupo] = respuesta.context["grupos"]
        self.assertEqual(sorted(f["comision"] for f in grupo["filas"]), [Decimal("20.00"), Decimal("50.00")])
