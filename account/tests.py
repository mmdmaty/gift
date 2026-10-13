from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import CumstomUserModel, SiteSettings


class SignupTests(TestCase):
    def test_signup_allowed_creates_user(self):
        SiteSettings.get()

        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ساخت اکانت")

        response = self.client.post(
            reverse("signup"),
            {
                "username": "testuser",
                "password1": "Raha-Gift-2026!",
                "password2": "Raha-Gift-2026!",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(CumstomUserModel.objects.filter(username="testuser").exists())

    def test_signup_blocked_shows_message_and_creates_nothing(self):
        site_settings = SiteSettings.get()
        site_settings.allow_registration = False
        site_settings.save()

        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ساخت اکانت امکان پذیر نیست")

        response = self.client.post(
            reverse("signup"),
            {
                "username": "blockeduser",
                "password1": "Raha-Gift-2026!",
                "password2": "Raha-Gift-2026!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CumstomUserModel.objects.filter(username="blockeduser").exists())


class LoginSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        CumstomUserModel.objects.create_user(username="alice", password="Qu1et-River-88x")

    def _post(self, password, **extra):
        return self.client.post(
            reverse("login"),
            {"username": "alice", "password": password},
            **extra,
        )

    def test_valid_login_redirects(self):
        response = self._post("Qu1et-River-88x")
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_five_failures_lock_out_ip_even_with_correct_password(self):
        for _ in range(4):
            self.assertEqual(self._post("wrong").status_code, 200)
        self.assertEqual(self._post("wrong").status_code, 429)

        response = self._post("Qu1et-River-88x")
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "موقتاً مسدود", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

        # other IPs are unaffected
        response = self._post("Qu1et-River-88x", REMOTE_ADDR="10.0.0.2")
        self.assertEqual(response.status_code, 302)

    def test_failure_shows_attempts_left(self):
        response = self._post("wrong")
        self.assertContains(response, "1 از 5 تلاش ناموفق")
        self.assertContains(response, "4 تلاش دیگر باقی مانده است")

        response = self._post("wrong")
        self.assertContains(response, "3 تلاش دیگر باقی مانده است")

    def test_lockout_still_active_before_ten_minutes(self):
        for _ in range(5):
            self._post("wrong")
        with mock.patch("account.security.time.time", return_value=__import__("time").time() + 590):
            response = self._post("Qu1et-River-88x")
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "1 دقیقه", status_code=429)

    def test_lockout_expires_after_ten_minutes(self):
        for _ in range(5):
            self._post("wrong")
        with mock.patch("account.security.time.time", return_value=__import__("time").time() + 601):
            response = self._post("Qu1et-River-88x")
        self.assertEqual(response.status_code, 302)

    def test_success_resets_failure_count(self):
        for _ in range(4):
            self._post("wrong")
        self._post("Qu1et-River-88x")
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self._post("wrong").status_code, 200)
