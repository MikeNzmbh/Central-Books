from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


User = get_user_model()


class AdminAccessTests(TestCase):
    @override_settings(ENABLE_DJANGO_ADMIN=True, ROOT_URLCONF="minibooks_project.urls")
    def test_admin_allows_superuser(self):
        superuser = User.objects.create_superuser(
            username="super-admin",
            email="super@example.com",
            password="password123",
        )
        self.client.force_login(superuser)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)

    @override_settings(ENABLE_DJANGO_ADMIN=True, ROOT_URLCONF="minibooks_project.urls")
    def test_admin_blocks_non_superuser(self):
        user = User.objects.create_user(
            username="regular-user",
            email="user@example.com",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"restricted to superusers", response.content)

    @override_settings(ENABLE_DJANGO_ADMIN=False, ROOT_URLCONF="minibooks_project.urls")
    def test_admin_disabled_returns_404(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 404)
