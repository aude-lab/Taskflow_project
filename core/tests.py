from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from projects.models import Project
from tasks.models import Task

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


class DashboardHomeTestCase(TestCase):
    """Tests du tableau de bord sur l'accueil (cf. core/SPEC-front-dashboard.md).

    On teste ce que la PAGE rend ; la matrice fine des bornes de dates est déjà
    couverte par les tests API (tasks.tests.DashboardTestCase).
    """

    PASSWORD = "Brouillard-Tuile-42"

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=self.PASSWORD
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password=self.PASSWORD
        )
        self.project = Project.objects.create(owner=self.alice, name="Projet Alice")
        self.bob_project = Project.objects.create(owner=self.bob, name="Projet Bob")
        # Même source de date que la vue, pour éviter tout écart près de minuit.
        self.today = timezone.localdate()
        self.url = reverse("home")
        self.client.force_login(self.alice)

    def make_task(self, project=None, days=None, status=None, title="T"):
        due = None if days is None else self.today + timedelta(days=days)
        return Task.objects.create(
            title=title,
            project=project or self.project,
            due_date=due,
            status=status or Task.Status.TODO,
        )

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_empty_dashboard(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["overdue"]), [])
        self.assertEqual(list(response.context["upcoming"]), [])
        self.assertEqual(
            response.context["by_status"],
            {Task.Status.TODO: 0, Task.Status.IN_PROGRESS: 0, Task.Status.DONE: 0},
        )
        self.assertContains(response, "Aucune tâche en retard.")
        self.assertContains(response, "Aucune tâche à venir.")
        # Le commentaire du partial ne doit jamais apparaître dans la page
        # (un {# #} multi-ligne se rendait littéralement — corrigé en
        # {% comment %}).
        self.assertNotContains(response, "itérable de Task")

    def test_overdue_unfinished_task_appears_in_overdue_only(self):
        overdue = self.make_task(days=-3, title="Rapport en retard")
        response = self.client.get(self.url)
        self.assertIn(overdue, response.context["overdue"])
        self.assertNotIn(overdue, response.context["upcoming"])
        self.assertContains(response, "Rapport en retard")

    def test_overdue_but_done_is_excluded(self):
        self.make_task(days=-3, status=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["overdue"]), [])

    def test_upcoming_task_appears(self):
        upcoming = self.make_task(days=7, title="Réunion à venir")
        response = self.client.get(self.url)
        self.assertIn(upcoming, response.context["upcoming"])
        self.assertContains(response, "Réunion à venir")

    def test_by_status_uses_accented_labels(self):
        self.make_task(status=Task.Status.IN_PROGRESS)
        response = self.client.get(self.url)
        # Libellés du modèle, jamais les valeurs ASCII.
        self.assertContains(response, "En cours")
        self.assertNotContains(response, "en_cours")
        self.assertEqual(response.context["by_status"][Task.Status.IN_PROGRESS], 1)

    def test_isolation_other_users_tasks_never_shown(self):
        self.make_task(project=self.bob_project, days=-3, title="Secret de Bob")
        self.make_task(project=self.bob_project, days=5)
        self.make_task(project=self.bob_project, status=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["overdue"]), [])
        self.assertEqual(list(response.context["upcoming"]), [])
        self.assertEqual(
            response.context["by_status"],
            {Task.Status.TODO: 0, Task.Status.IN_PROGRESS: 0, Task.Status.DONE: 0},
        )
        self.assertNotContains(response, "Secret de Bob")
