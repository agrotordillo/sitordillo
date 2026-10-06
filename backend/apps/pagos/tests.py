from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.cobros.forms import CobroForm
from apps.compras.models import OrdenCompra
from apps.fiscal.models import FormaPago, RegimenFiscal
from apps.gastos.forms import GastoForm
from apps.pagos.forms import EnviarComprobanteForm, PagoEditForm, PagoForm, PagoMultipleForm
from apps.pagos.models import CuentaPorPagar, Pago
from apps.proveedores.models import Proveedor

User = get_user_model()

PDF = b"%PDF-1.4\n%comprobante\n"


class EnviarComprobanteTests(TestCase):
    """B13 (docs/AUDITORIA.md): con solo "ver pagos" se mandaba, desde la
    cuenta de la empresa, un correo a cualquiera con cualquier adjunto."""

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
        cuenta = CuentaPorPagar.objects.create(
            orden_compra=orden, monto_total=Decimal("100.00"),
            fecha_emision=date(2026, 9, 2), fecha_vencimiento=date(2026, 10, 2),
        )
        efectivo = FormaPago.objects.get_or_create(clave="01", defaults={"descripcion": "Efectivo"})[0]
        cls.pago = Pago.objects.create(
            cuenta_por_pagar=cuenta, fecha_pago=date(2026, 9, 3), monto_pagado=Decimal("10.00"), forma_pago=efectivo,
        )
        cls.pagos = User.objects.create_user(username="pagos", password="S3guridad!2026")
        cls.pagos.groups.add(Group.objects.get(name="Pagos"))
        cls.solo_ver = User.objects.create_user(username="solo_ver", password="S3guridad!2026")
        cls.solo_ver.user_permissions.add(Permission.objects.get(codename="view_pago"))

    def _enviar(self, usuario, *adjuntos, cc=""):
        self.client.force_login(usuario)
        return self.client.post(reverse("pagos:pago-enviar-correo"), {
            "pago_ids": [self.pago.pk], "destinatario": "proveedor@example.com", "cc": cc,
            "adjuntos": list(adjuntos), "next": reverse("pagos:cuenta-list"),
        })

    def test_solo_quien_registra_pagos_envia_correos(self):
        respuesta = self._enviar(self.solo_ver, SimpleUploadedFile("pago.pdf", PDF))
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_envia_un_pdf_con_el_tipo_segun_su_extension(self):
        self._enviar(self.pagos, SimpleUploadedFile("pago.pdf", PDF, content_type="text/html"))

        self.assertEqual(len(mail.outbox), 1)
        # El logo va como MIMEImage aparte; los archivos subidos, como tuplas.
        adjuntos = [tuple(a) for a in mail.outbox[0].attachments if isinstance(a, tuple)]
        self.assertEqual(adjuntos, [("pago.pdf", PDF, "application/pdf")])

    def test_rechaza_tipos_y_contenidos_no_permitidos(self):
        for adjunto in (
            SimpleUploadedFile("pagina.html", b"<script>alert(1)</script>"),
            SimpleUploadedFile("factura.pdf", b"MZ\x90\x00 esto es un ejecutable"),
        ):
            self._enviar(self.pagos, adjunto)
        self.assertEqual(len(mail.outbox), 0)

    def test_limites_de_tamano_adjuntos_y_copias(self):
        grande = SimpleUploadedFile("grande.pdf", PDF + b"0" * EnviarComprobanteForm.MAX_BYTES_POR_ADJUNTO)
        self._enviar(self.pagos, grande)
        muchos = [SimpleUploadedFile(f"p{i}.pdf", PDF) for i in range(EnviarComprobanteForm.MAX_ADJUNTOS + 1)]
        self._enviar(self.pagos, *muchos)
        copias = ",".join(f"c{i}@example.com" for i in range(EnviarComprobanteForm.MAX_CC + 1))
        self._enviar(self.pagos, SimpleUploadedFile("pago.pdf", PDF), cc=copias)
        self.assertEqual(len(mail.outbox), 0)


class ComprobantesSubidosTests(TestCase):
    """B32 (docs/AUDITORIA.md), decisión del usuario: los comprobantes de
    pagos, cobros y gastos aceptan PDF, XML, JPG o PNG de hasta 10 MB,
    revisados por extensión y contenido. Lo ya guardado no se vuelve a
    revisar al editar."""

    FORMULARIOS = (PagoForm, PagoEditForm, PagoMultipleForm, CobroForm, GastoForm)

    def _errores(self, formulario, archivo, **kwargs):
        form = formulario(data={}, files={"comprobante": archivo}, **kwargs)
        form.is_valid()
        return form.errors.get("comprobante")

    def test_rechaza_lo_que_no_es_un_comprobante(self):
        for formulario in self.FORMULARIOS:
            with self.subTest(formulario.__name__):
                self.assertEqual(formulario().fields["comprobante"].widget.attrs["accept"], ".jpeg,.jpg,.pdf,.png,.xml")
                self.assertTrue(self._errores(formulario, SimpleUploadedFile("pagina.html", b"<script></script>")))
                self.assertTrue(self._errores(formulario, SimpleUploadedFile("vale.pdf", b"MZ\x90\x00 ejecutable")))
                grande = SimpleUploadedFile("vale.pdf", PDF + b"0" * (10 * 1024 * 1024))
                self.assertTrue(self._errores(formulario, grande))
                self.assertIsNone(self._errores(formulario, SimpleUploadedFile("vale.pdf", PDF)))

    def test_el_comprobante_ya_guardado_no_se_revisa_al_editar(self):
        pago = Pago(comprobante="pagos/comprobantes/abc/recibo-viejo.doc")
        form = PagoEditForm(data={}, instance=pago)
        form.is_valid()
        self.assertNotIn("comprobante", form.errors)
