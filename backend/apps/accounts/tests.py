from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from axes.models import AccessAttempt
from axes.utils import reset

from apps.accounts.models import AsignacionSucursal
from apps.products.models import Almacen

User = get_user_model()


class UserModelTests(TestCase):
    def test_can_create_user(self):
        user = User.objects.create_user(username='vet1', password='S3guridad!2026')
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.username, 'vet1')

    def test_password_is_not_stored_in_plain_text(self):
        user = User.objects.create_user(username='vet2', password='S3guridad!2026')
        self.assertNotEqual(user.password, 'S3guridad!2026')
        self.assertNotIn('S3guridad!2026', user.password)

    def test_check_password_works(self):
        user = User.objects.create_user(username='vet3', password='S3guridad!2026')
        self.assertTrue(user.check_password('S3guridad!2026'))
        self.assertFalse(user.check_password('otra-clave'))

    def test_password_uses_argon2(self):
        user = User.objects.create_user(username='vet4', password='S3guridad!2026')
        self.assertTrue(user.password.startswith('argon2$'))
        self.assertEqual(user.password.split('$')[0], Argon2PasswordHasher.algorithm)


class LoginTests(TestCase):
    def setUp(self):
        self.password = 'S3guridad!2026'
        self.user = User.objects.create_user(username='mostrador', password=self.password)
        self.login_url = reverse('accounts:login')
        self.protected_url = reverse('home')

    def tearDown(self):
        reset()

    def test_correct_login_authenticates_user(self):
        response = self.client.post(
            self.login_url,
            {'username': 'mostrador', 'password': self.password},
        )
        self.assertRedirects(response, self.protected_url, fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)

    def test_incorrect_login_does_not_authenticate(self):
        response = self.client.post(
            self.login_url,
            {'username': 'mostrador', 'password': 'clave-incorrecta'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(response.context['form'].errors)

    def test_anonymous_user_is_redirected_from_protected_view(self):
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_authenticated_user_can_access_protected_view(self):
        self.client.post(self.login_url, {'username': 'mostrador', 'password': self.password})
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, 200)

    def test_logout_ends_session(self):
        self.client.post(self.login_url, {'username': 'mostrador', 'password': self.password})
        self.client.post(reverse('accounts:logout'))
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)


class AxesLockoutTests(TestCase):
    def setUp(self):
        self.password = 'S3guridad!2026'
        self.user = User.objects.create_user(username='cajero', password=self.password)
        self.login_url = reverse('accounts:login')

    def tearDown(self):
        reset()

    def test_failed_attempts_are_recorded(self):
        self.client.post(self.login_url, {'username': 'cajero', 'password': 'mala-clave'})
        self.assertTrue(AccessAttempt.objects.filter(username='cajero').exists())

    def test_lockout_after_failure_limit(self):
        for _ in range(5):
            self.client.post(self.login_url, {'username': 'cajero', 'password': 'mala-clave'})

        self.client.post(self.login_url, {'username': 'cajero', 'password': self.password})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_correct_login_succeeds_when_not_locked_out(self):
        self.client.post(self.login_url, {'username': 'cajero', 'password': 'mala-clave'})
        response = self.client.post(self.login_url, {'username': 'cajero', 'password': self.password})
        self.assertIn('_auth_user_id', self.client.session)


class SucursalPrincipalTests(TestCase):
    """B21 (docs/AUDITORIA.md): al crear un usuario con dos sucursales ambas
    quedaban como principales, mover la principal exigía dos guardados y un
    Administrador podía quitarse su propio acceso."""

    @classmethod
    def setUpTestData(cls):
        cls.centro = Almacen.objects.create(nombre="Sucursal Centro", tipo=Almacen.Tipo.SUCURSAL, numero=1)
        cls.norte = Almacen.objects.create(nombre="Sucursal Norte", tipo=Almacen.Tipo.SUCURSAL, numero=2)
        cls.admin = User.objects.create_superuser(username="admin", password="S3guridad!2026")

    def setUp(self):
        self.client.force_login(self.admin)

    def _asignaciones(self, filas, iniciales=0):
        datos = {
            "asignaciones-TOTAL_FORMS": len(filas), "asignaciones-INITIAL_FORMS": iniciales,
            "asignaciones-MIN_NUM_FORMS": 0, "asignaciones-MAX_NUM_FORMS": 1000,
        }
        for i, fila in enumerate(filas):
            for campo, valor in fila.items():
                datos[f"asignaciones-{i}-{campo}"] = valor
        return datos

    def test_alta_con_dos_principales_se_rechaza(self):
        respuesta = self.client.post(reverse("accounts:usuario-create"), {
            "username": "cajero", "password1": "S3guridad!2026", "password2": "S3guridad!2026",
            **self._asignaciones([
                {"almacen": self.centro.pk, "es_principal": "on"},
                {"almacen": self.norte.pk, "es_principal": "on"},
            ]),
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Solo una sucursal puede ser la principal", str(respuesta.context["formset"].non_form_errors()))
        self.assertFalse(User.objects.filter(username="cajero").exists())

    def test_mover_la_principal_en_un_solo_guardado(self):
        usuario = User.objects.create_user(username="cajero", password="S3guridad!2026")
        centro = AsignacionSucursal.objects.create(usuario=usuario, almacen=self.centro, es_principal=True)
        norte = AsignacionSucursal.objects.create(usuario=usuario, almacen=self.norte, es_principal=False)

        respuesta = self.client.post(reverse("accounts:usuario-update", args=[usuario.pk]), {
            "username": "cajero",
            **self._asignaciones([
                {"id": centro.pk, "almacen": self.centro.pk},
                {"id": norte.pk, "almacen": self.norte.pk, "es_principal": "on"},
            ], iniciales=2),
        })

        self.assertRedirects(respuesta, reverse("accounts:usuario-list"), fetch_redirect_response=False)
        principales = AsignacionSucursal.objects.filter(usuario=usuario, es_principal=True)
        self.assertEqual([a.almacen for a in principales], [self.norte])

    def test_la_base_de_datos_no_admite_dos_principales(self):
        usuario = User.objects.create_user(username="cajero", password="S3guridad!2026")
        AsignacionSucursal.objects.create(usuario=usuario, almacen=self.centro, es_principal=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AsignacionSucursal.objects.create(usuario=usuario, almacen=self.norte, es_principal=True)

    def test_el_administrador_no_puede_quitarse_su_propio_acceso(self):
        respuesta = self.client.post(reverse("accounts:usuario-update", args=[self.admin.pk]), {
            "username": "admin", **self._asignaciones([]),
        })

        self.assertRedirects(respuesta, reverse("accounts:usuario-list"), fetch_redirect_response=False)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)
        self.assertContains(
            self.client.get(reverse("accounts:usuario-update", args=[self.admin.pk])),
            "No puedes quitarte tu propio acceso de Administrador",
        )

    def test_si_puede_quitarselo_a_otro_administrador(self):
        otro = User.objects.create_superuser(username="otro", password="S3guridad!2026")
        respuesta = self.client.post(reverse("accounts:usuario-update", args=[otro.pk]), {
            "username": "otro", **self._asignaciones([]),
        })

        self.assertRedirects(respuesta, reverse("accounts:usuario-list"), fetch_redirect_response=False)
        otro.refresh_from_db()
        self.assertFalse(otro.is_superuser)
