from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.test import TestCase
from django.urls import reverse

from axes.models import AccessAttempt
from axes.utils import reset

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
