import shutil
import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import openpyxl

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import AsignacionSucursal
from apps.products.models import Almacen, PuntoVenta, Turno

from apps.gastos import importacion
from apps.gastos.models import BitacoraAccesoGastos, CentroCosto, ConceptoGasto, Gasto
from apps.gastos.services import gasto_directo_por_centro

User = get_user_model()


class GastoTests(TestCase):
    """Reglas del módulo de gastos sobre el catálogo que cargan las
    migraciones de datos (conceptos, grupos y centros no sucursal)."""

    @classmethod
    def setUpTestData(cls):
        cls.almacen = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.caja = PuntoVenta.objects.create(almacen=cls.almacen, codigo="C1", numero=1, nombre="Caja 1")
        cls.sucursal = CentroCosto.objects.create(
            nombre="Sucursal Centro", tipo=CentroCosto.Tipo.SUCURSAL, almacen=cls.almacen,
        )
        cls.administracion = CentroCosto.objects.get(codigo="ADM")
        cls.personal = CentroCosto.objects.get(codigo="PER")
        cls.agua = ConceptoGasto.objects.get(nombre="Agua")
        cls.gasto_medico = ConceptoGasto.objects.get(nombre="Gastos Médicos")
        cls.terreno = ConceptoGasto.objects.get(nombre="Terrenos")
        cls.isr = ConceptoGasto.objects.get(nombre="ISR por Actividad Empresarial")

        cls.capturista = User.objects.create_user(username="capturista", password="S3guridad!2026")
        cls.capturista.groups.add(Group.objects.get(name="Gastos"))

    def setUp(self):
        self.client.force_login(self.capturista)
        self.turno = Turno.objects.create(punto_venta=self.caja, usuario=self.capturista)

    def _gasto(self, concepto, importe, centro=None, **campos):
        centro = centro or self.sucursal
        turno = self.turno if centro.tipo == CentroCosto.Tipo.SUCURSAL else None
        gasto = Gasto(
            centro_costo=centro, concepto_gasto=concepto, turno=turno, descripcion="Vale de prueba",
            fecha=date(2026, 9, 15), importe=Decimal(importe), **campos,
        )
        gasto.full_clean()
        gasto.save()
        return gasto

    def _datos_formulario(self, gasto, **cambios):
        datos = {
            "centro_costo": gasto.centro_costo_id,
            "concepto_gasto": gasto.concepto_gasto_id,
            "turno": gasto.turno_id or "",
            "descripcion": gasto.descripcion,
            "condicion": gasto.condicion,
            "fecha": gasto.fecha.isoformat(),
            "importe": str(gasto.importe),
            "distribuciones-TOTAL_FORMS": "0",
            "distribuciones-INITIAL_FORMS": "0",
            "distribuciones-MIN_NUM_FORMS": "0",
            "distribuciones-MAX_NUM_FORMS": "1000",
        }
        datos.update(cambios)
        return datos

    def test_gasto_se_edita_aunque_su_turno_ya_este_cerrado(self):
        gasto = self._gasto(self.agua, "60.00")
        gasto.turno.cerrar()

        respuesta = self.client.post(
            reverse("gastos:gasto-update", args=[gasto.pk]),
            self._datos_formulario(gasto, condicion=Gasto.Condicion.PAGADO),
        )

        self.assertRedirects(respuesta, reverse("gastos:gasto-list"))
        gasto.refresh_from_db()
        self.assertEqual(gasto.condicion, Gasto.Condicion.PAGADO)

    def test_turno_cerrado_no_se_ofrece_en_un_alta(self):
        self.turno.cerrar()

        respuesta = self.client.get(reverse("gastos:gasto-create"))

        self.assertNotIn(self.turno, respuesta.context["form"].fields["turno"].queryset)

    def test_gasto_personal_no_se_carga_a_una_sucursal(self):
        with self.assertRaises(ValidationError) as error:
            self._gasto(self.gasto_medico, "500.00")
        self.assertIn("centro_costo", error.exception.message_dict)

        self._gasto(self.gasto_medico, "500.00", centro=self.personal)

    def test_gasto_personal_compartido_no_se_reparte_a_otro_tipo_de_centro(self):
        datos = {
            "centro_costo": self.administracion.pk,
            "concepto_gasto": self.gasto_medico.pk,
            "descripcion": "Consulta médica",
            "condicion": Gasto.Condicion.PENDIENTE,
            "fecha": "2026-09-15",
            "importe": "1000.00",
            "es_compartido": "on",
            "distribuciones-TOTAL_FORMS": "2",
            "distribuciones-INITIAL_FORMS": "0",
            "distribuciones-MIN_NUM_FORMS": "0",
            "distribuciones-MAX_NUM_FORMS": "1000",
            "distribuciones-0-centro_costo": self.personal.pk,
            "distribuciones-0-monto": "600.00",
            "distribuciones-1-centro_costo": self.administracion.pk,
            "distribuciones-1-monto": "400.00",
        }

        respuesta = self.client.post(reverse("gastos:gasto-create"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].non_field_errors())
        self.assertFalse(Gasto.objects.filter(descripcion="Consulta médica").exists())

    def test_punto_de_equilibrio_solo_suma_gasto_de_operacion(self):
        self._gasto(self.agua, "200.00")
        self._gasto(self.terreno, "5000.00")
        self._gasto(self.isr, "800.00")

        total = gasto_directo_por_centro(self.sucursal, date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(total, Decimal("200.00"))

    def test_grupo_gastos_solo_consulta_el_catalogo_de_conceptos(self):
        lista = self.client.get(reverse("gastos:concepto-list"))

        self.assertEqual(lista.status_code, 200)
        self.assertNotContains(lista, reverse("gastos:concepto-create"))
        self.assertEqual(self.client.get(reverse("gastos:concepto-create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("gastos:concepto-update", args=[self.agua.pk])).status_code, 403,
        )


class AccesoEstrictoTests(TestCase):
    """Gastos es un módulo de permisos estrictos: ni el Administrador entra
    sin su capacidad asignada, y solo la puede dar o quitar quien ya la
    tiene (ver apps.core.permisos_estrictos)."""

    @classmethod
    def setUpTestData(cls):
        cls.captura = Group.objects.get(name="Gastos")
        cls.administracion = Group.objects.get(name="Gastos - Administración")
        cls.admin_sin_acceso = User.objects.create_superuser(username="jefe", password="S3guridad!2026")
        cls.custodio = User.objects.create_superuser(username="custodio", password="S3guridad!2026")
        cls.custodio.groups.add(cls.captura, cls.administracion)
        cls.empleado = User.objects.create_user(username="empleado", password="S3guridad!2026")

    def _editar_usuario(self, usuario, grupos, **extra):
        datos = {
            "username": usuario.username,
            "first_name": "",
            "last_name": "",
            "email": "",
            "groups": [g.pk for g in grupos],
            "password1": "",
            "password2": "",
            "asignaciones-TOTAL_FORMS": "0",
            "asignaciones-INITIAL_FORMS": "0",
            "asignaciones-MIN_NUM_FORMS": "0",
            "asignaciones-MAX_NUM_FORMS": "1000",
        }
        datos.update(extra)
        return self.client.post(reverse("accounts:usuario-update", args=[usuario.pk]), datos)

    def test_administrador_sin_capacidad_no_entra_ni_ve_el_modulo(self):
        self.client.force_login(self.admin_sin_acceso)

        for nombre in ("gasto-list", "gasto-create", "reporte", "concepto-list", "bitacora-acceso-list"):
            self.assertEqual(self.client.get(reverse(f"gastos:{nombre}")).status_code, 403, nombre)
        self.assertNotContains(self.client.get(reverse("home")), reverse("gastos:gasto-list"))

    def test_administrador_con_capacidad_si_entra(self):
        self.client.force_login(self.custodio)

        self.assertEqual(self.client.get(reverse("gastos:gasto-list")).status_code, 200)
        self.assertContains(self.client.get(reverse("home")), reverse("gastos:gasto-list"))

    def test_administrador_sin_acceso_no_puede_darselo_ni_a_si_mismo(self):
        self.client.force_login(self.admin_sin_acceso)

        self._editar_usuario(self.admin_sin_acceso, [self.captura])
        self._editar_usuario(self.empleado, [self.captura])

        self.assertFalse(self.admin_sin_acceso.groups.filter(pk=self.captura.pk).exists())
        self.assertFalse(self.empleado.groups.filter(pk=self.captura.pk).exists())

    def test_administrador_sin_acceso_no_se_lo_quita_a_otro_ni_le_cambia_la_contrasena(self):
        self.client.force_login(self.admin_sin_acceso)

        self._editar_usuario(
            self.custodio, [], is_superuser="on", password1="Otra!Clave2026", password2="Otra!Clave2026",
        )

        self.custodio.refresh_from_db()
        self.assertTrue(self.custodio.groups.filter(pk=self.captura.pk).exists())
        self.assertTrue(self.custodio.check_password("S3guridad!2026"))

    def test_quien_tiene_acceso_lo_da_y_queda_en_la_bitacora(self):
        self.client.force_login(self.custodio)

        self._editar_usuario(self.empleado, [self.captura])

        self.assertTrue(self.empleado.groups.filter(pk=self.captura.pk).exists())
        registro = BitacoraAccesoGastos.objects.get(usuario=self.empleado)
        self.assertEqual(registro.accion, BitacoraAccesoGastos.Accion.OTORGADA)
        self.assertEqual(registro.realizado_por, self.custodio)

    def test_comando_del_servidor_otorga_el_acceso(self):
        call_command("otorgar_acceso_gastos", "jefe", stdout=StringIO())

        self.assertTrue(self.admin_sin_acceso.has_perm("gastos.view_gasto"))
        self.assertEqual(
            BitacoraAccesoGastos.objects.filter(usuario=self.admin_sin_acceso, realizado_por__isnull=True).count(), 2,
        )

    def test_admin_de_django_no_administra_usuarios_ni_grupos(self):
        self.assertFalse(admin.site.is_registered(Group))
        self.assertFalse(admin.site.is_registered(User))


class AlcancePorSucursalTests(TestCase):
    """B09 y B11 (docs/AUDITORIA.md): un usuario de Gastos restringido a su
    sucursal abría por URL -y descargaba el comprobante de- gastos de otros
    centros de costo, incluidos los corporativos."""

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
        cls.almacen = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.caja = PuntoVenta.objects.create(almacen=cls.almacen, codigo="C1", numero=1, nombre="Caja 1")
        cls.sucursal = CentroCosto.objects.create(
            nombre="Sucursal Centro", tipo=CentroCosto.Tipo.SUCURSAL, almacen=cls.almacen,
        )
        cls.administracion = CentroCosto.objects.get(codigo="ADM")
        cls.agua = ConceptoGasto.objects.get(nombre="Agua")
        cls.capturista = User.objects.create_user(username="capturista", password="S3guridad!2026")
        cls.capturista.groups.add(Group.objects.get(name="Gastos"))
        AsignacionSucursal.objects.create(usuario=cls.capturista, almacen=cls.almacen)
        cls.turno = Turno.objects.create(punto_venta=cls.caja, usuario=cls.capturista)

    def _gasto(self, centro, descripcion):
        return Gasto.objects.create(
            centro_costo=centro, concepto_gasto=self.agua, descripcion=descripcion, fecha=date(2026, 9, 15),
            importe=Decimal("100.00"), turno=self.turno if centro == self.sucursal else None,
            comprobante=SimpleUploadedFile("vale.pdf", b"%PDF-1.4\n"),
        )

    def test_no_abre_ni_descarga_gastos_de_otros_centros(self):
        propio = self._gasto(self.sucursal, "Agua de la sucursal")
        ajeno = self._gasto(self.administracion, "Bono confidencial")
        self.client.force_login(self.capturista)

        self.assertEqual(self.client.get(reverse("gastos:gasto-update", args=[propio.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("gastos:gasto-update", args=[ajeno.pk])).status_code, 404)
        self.assertEqual(self.client.get(propio.comprobante.url).status_code, 200)
        self.assertEqual(self.client.get(ajeno.comprobante.url).status_code, 404)

    def test_ni_el_administrador_descarga_comprobantes_sin_la_capacidad_de_gastos(self):
        gasto = self._gasto(self.administracion, "Bono confidencial")
        self.client.force_login(User.objects.create_superuser(username="admin", password="S3guridad!2026"))
        self.assertEqual(self.client.get(gasto.comprobante.url).status_code, 404)


class ImportacionValesTests(TestCase):
    """Importación en dos pasos de los vales del Excel de pólizas: propuesta
    en un Excel de revisión y, ya revisado, importación de lo marcado."""

    @classmethod
    def setUpTestData(cls):
        for numero, (nombre, codigo) in enumerate((("BODEGA SUR", "BSU"), ("LERDO", "LER")), start=1):
            almacen = Almacen.objects.create(nombre=nombre, tipo=Almacen.Tipo.SUCURSAL, numero=numero)
            CentroCosto.objects.create(
                codigo=codigo, nombre=nombre.title(), tipo=CentroCosto.Tipo.SUCURSAL, almacen=almacen,
            )

    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.polizas = Path(self.carpeta.name) / "polizas.xlsx"
        self.revision = Path(self.carpeta.name) / "revision.xlsx"
        libro = openpyxl.Workbook()
        hoja = libro.active
        hoja.title = "GASTOS SF SUCURSALES"
        encabezado = ["VALE", "CONCEPTO", "CENTRO DE COSTO", "IMPORTE", "CONDICION", "TURNO",
                      "FACTURA DONDE SALE EL GASTO"]
        for fila in [
            ["GASTOS DE SUCURSALES SIN FACTURA MES DE NOVIEMBRE 2025"],
            encabezado,
            [100, "PAGO DE POLICIA LERDO", "LERDO", 50, "BODEGA SUR 28/11/2026", 1, "F1"],
            ["GASTOS DE SUCURSALES SIN FACTURA MES DE ENERO 2026"],
            encabezado,
            [101, "PAGO DE POLICIA BODEGA SUR Y LERDO", "BODEGA-LERDO", 100, "BODEGA SUR 05/01/2026", 49001, "0201F1"],
            [102, "VIATICO A DON MARTIN AL BANCO", "LKERDO", 40, "BODEGA SUR 06/01/2026", 49002, "0201F2"],
            [103, "PAGO DE AGUA GARRAFON", "BODEGA SUR", 60, "BODEGA SUR 07/01/2026", 49003, "0201F3"],
            [103, "PAGO DE AGUA GARRAFON", "BODEGA SUR", 60, "BODEGA SUR 07/01/2026", 49003, "0201F3"],
            [104, "PAGO DE LUZ", "BODEGA SUR", 300, "BODEGA SUR 08/01/2026", 49004, "0201F4"],
            [104, "PAGO DE LUZ", "BODEGA SUR", 120, "BODEGA SUR 08/01/2026", 49004, "0201F4"],
            [105, "COMPRA DE ACCESORIOS PARA MASCOTA VTA SUCURSALES", "SUCURSALES", 309, "BODEGA SUR 09/01/2026", 49005, "0201F5"],
            [106, "COMPRA DE REFRESCO PARA VENTA", "BODEGA SUR", 900, "BODEGA SUR 09/01/2026", 49005, "0201F5"],
            [107, "ALGO SIN REGLA", "BODEGA SUR", 10, "BODEGA SUR 10/01/2026", 49006, "0201F6"],
            [None, None, None, 1839, None, None, None],
        ]:
            hoja.append(fila)
        fiscal = libro.create_sheet("GASTOS FISCALES")
        fiscal.append(["GASTOS CON FACTURAS SUCURSALES FEBRERO 2026"])
        fiscal.append(encabezado)
        fiscal.append([200, "COMPRA DE PAPELERIA", "LERDO", 250, "BODEGA SUR 03/02/2026", 49100, "0201F9"])
        libro.save(self.polizas)

    def _generar(self):
        call_command(
            "generar_revision_gastos", excel=str(self.polizas), anio=2026, salida=str(self.revision),
            fecha_corte="2026-08-26", stdout=StringIO(),
        )
        return {fila["clave"]: fila for fila in importacion.leer_revision(self.revision)}

    def _guardar_revision(self, cambios):
        """`cambios`: {clave: {columna: valor}} sobre el archivo generado."""
        libro = importacion.abrir_libro(self.revision)
        hoja = libro["Vales"]
        titulos = [importacion.normalizar(c.value) for c in hoja[1]]
        columna = {clave: titulos.index(importacion.normalizar(titulo)) for clave, titulo, _ in importacion.COLUMNAS}
        for fila in hoja.iter_rows(min_row=2):
            for nombre, valor in cambios.get(fila[0].value, {}).items():
                fila[columna[nombre]].value = valor
        libro.save(self.revision)

    def test_propuesta_aplica_las_reglas_acordadas(self):
        filas = self._generar()
        hoja = "GASTOS SF SUCURSALES"

        self.assertNotIn(f"{hoja}!3", filas)  # 28/11/2026 en sección de 2025: el año se corrige a 2025
        self.assertEqual(filas[f"{hoja}!6"]["accion"], "IMPORTAR")
        self.assertTrue(filas[f"{hoja}!6"]["centro"].startswith("BSU"))
        self.assertEqual(filas[f"{hoja}!6"]["concepto"], "Servicio de Vigilancia")
        self.assertTrue(filas[f"{hoja}!7"]["centro"].startswith("LER"))
        self.assertEqual(filas[f"{hoja}!8"]["accion"], "IMPORTAR")
        self.assertEqual(filas[f"{hoja}!9"]["accion"], "OMITIR")  # duplicado exacto
        self.assertEqual(filas[f"{hoja}!10"]["accion"], "REVISAR")  # mismo vale, importes distintos
        self.assertEqual(filas[f"{hoja}!11"]["accion"], "REVISAR")
        self.assertEqual(filas[f"{hoja}!12"]["accion"], "OMITIR")  # mercancía para venta (y sin sucursal)
        self.assertEqual(filas[f"{hoja}!13"]["accion"], "OMITIR")
        self.assertEqual(filas[f"{hoja}!14"]["accion"], "REVISAR")  # sin concepto
        self.assertEqual(filas["GASTOS FISCALES!3"]["facturado"], "SI")
        self.assertEqual(filas["GASTOS FISCALES!3"]["referencia_factura"], importacion.FOLIO_PENDIENTE)
        self.assertEqual(filas[f"{hoja}!6"]["facturado"], "NO")

    def test_importa_lo_revisado_una_sola_vez(self):
        self._generar()
        self._guardar_revision({
            "GASTOS SF SUCURSALES!14": {"accion": "IMPORTAR", "concepto": "Artículos de Limpieza"},
        })

        call_command("importar_gastos_revisados", str(self.revision), stdout=StringIO())
        self.assertEqual(Gasto.objects.count(), 0)  # sin --aplicar solo valida

        call_command("importar_gastos_revisados", str(self.revision), aplicar=True, stdout=StringIO())
        call_command("importar_gastos_revisados", str(self.revision), aplicar=True, stdout=StringIO())

        self.assertEqual(Gasto.objects.count(), 5)
        policia = Gasto.objects.get(clave_importacion="GASTOS SF SUCURSALES!6")
        self.assertTrue(policia.importado)
        self.assertIsNone(policia.turno)
        self.assertEqual(policia.turno_anterior, "49001")
        self.assertEqual(policia.factura_caja_anterior, "0201F1")
        self.assertEqual(policia.condicion, Gasto.Condicion.PAGADO)
        self.assertEqual(policia.centro_costo.codigo, "BSU")
        papeleria = Gasto.objects.get(clave_importacion="GASTOS FISCALES!3")
        self.assertTrue(papeleria.facturado)
        self.assertEqual(papeleria.referencia_factura, importacion.FOLIO_PENDIENTE)

    def test_con_una_fila_con_error_no_importa_nada(self):
        self._generar()
        self._guardar_revision({"GASTOS SF SUCURSALES!7": {"centro": "XXX - No existe"}})

        with self.assertRaises(CommandError):
            call_command("importar_gastos_revisados", str(self.revision), aplicar=True, stdout=StringIO())

        self.assertEqual(Gasto.objects.count(), 0)

    def test_gasto_importado_se_edita_sin_turno(self):
        self._generar()
        call_command("importar_gastos_revisados", str(self.revision), aplicar=True, stdout=StringIO())
        gasto = Gasto.objects.get(clave_importacion="GASTOS SF SUCURSALES!6")

        gasto.descripcion = "Policía de enero"
        gasto.full_clean()
