from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class HomeViewTestCase(TestCase):
    """Tests de l'accueil du front (cf. core/SPEC-front-base.md)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="aude", email="aude@example.com", password="Brouillard-Tuile-42"
        )
        self.url = reverse("home")

    def test_anonymous_is_redirected_to_login(self):
        # Garde-fou du LoginRequiredMixin : sans lui, la vue recevrait un
        # AnonymousUser et lèverait une 500 au lieu de rediriger.
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_sees_home(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "aude")
        self.assertTemplateUsed(response, "core/home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_navigation_shows_logout_when_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Déconnexion")
        self.assertContains(response, reverse("logout"))
