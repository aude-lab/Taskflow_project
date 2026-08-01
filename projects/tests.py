from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from tasks.models import Task

from .models import Project

User = get_user_model()


class ProjectAPITestCase(APITestCase):
    """Tests de la ressource Project (cf. projects/SPEC.md)."""

    def setUp(self):
        # L'email est unique en base (cf. accounts/SPEC.md) : chaque utilisateur
        # de test doit donc avoir le sien.
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.list_url = reverse("project-list")

    def detail_url(self, pk):
        return reverse("project-detail", args=[pk])

    # --- Cas nominal (CRUD) ---

    def test_create_project(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"name": "Refonte site"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Refonte site")
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner, self.alice)

    def test_list_only_own_projects(self):
        Project.objects.create(owner=self.alice, name="A1")
        Project.objects.create(owner=self.bob, name="B1")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "A1")

    def test_retrieve_own_project(self):
        project = Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "A1")

    def test_update_own_project(self):
        project = Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            self.detail_url(project.pk),
            {"name": "A1 renommé", "description": "maj"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "A1 renommé")
        self.assertEqual(project.description, "maj")

    def test_update_keeping_same_name(self):
        # Renommer un projet en gardant son propre nom ne doit pas déclencher
        # la validation d'unicité (exclusion de l'instance courante).
        project = Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(project.pk), {"description": "maj"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_partial_update_own_project(self):
        project = Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(project.pk), {"name": "A2"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.name, "A2")

    def test_delete_own_project(self):
        project = Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.delete(self.detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    # --- Cas limites / validation ---

    def test_create_empty_name(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"name": ""}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_name(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_name_too_long(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"name": "x" * 201}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_duplicate_name_same_user(self):
        Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"name": "A1"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_to_another_own_project_name(self):
        # Renommer un projet vers le nom d'un AUTRE de ses projets → 400
        # (couvre la branche exclude(pk=...) de validate_name en update).
        Project.objects.create(owner=self.alice, name="A1")
        project = Project.objects.create(owner=self.alice, name="A2")
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(project.pk), {"name": "A1"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_name_allowed_for_other_user(self):
        Project.objects.create(owner=self.alice, name="A1")
        self.client.force_authenticate(self.bob)
        response = self.client.post(
            self.list_url, {"name": "A1"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_without_description(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"name": "Sans desc"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["description"], "")

    # --- Permissions / isolation par utilisateur ---

    def test_cannot_retrieve_other_users_project(self):
        project = Project.objects.create(owner=self.bob, name="B1")
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_users_project(self):
        project = Project.objects.create(owner=self.bob, name="B1")
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            self.detail_url(project.pk), {"name": "hack"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_patch_other_users_project(self):
        project = Project.objects.create(owner=self.bob, name="B1")
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(project.pk), {"name": "hack"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_project(self):
        project = Project.objects.create(owner=self.bob, name="B1")
        self.client.force_authenticate(self.alice)
        response = self.client.delete(self.detail_url(project.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_owner_in_body_is_ignored(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"name": "Projet", "owner": self.bob.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner, self.alice)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProjectFrontTestCase(TestCase):
    """Tests du CRUD projets côté front (cf. projects/SPEC-front.md)."""

    PASSWORD = "Brouillard-Tuile-42"

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=self.PASSWORD
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password=self.PASSWORD
        )
        self.alice_project = Project.objects.create(
            owner=self.alice, name="Projet Alice"
        )
        self.bob_project = Project.objects.create(owner=self.bob, name="Projet Bob")
        self.client.force_login(self.alice)

    # --- Isolation ---

    def test_list_shows_only_own_projects(self):
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projet Alice")
        self.assertNotContains(response, "Projet Bob")

    def test_other_users_project_returns_404(self):
        for name in ("project_detail", "project_update", "project_delete"):
            with self.subTest(view=name):
                response = self.client.get(reverse(name, args=[self.bob_project.pk]))
                self.assertEqual(response.status_code, 404)

    def test_cannot_modify_other_users_project_via_post(self):
        # Les chemins destructeurs doivent être testés en POST, pas seulement
        # en GET : c'est par là qu'une requête forgée passerait.
        response = self.client.post(
            reverse("project_update", args=[self.bob_project.pk]),
            {"name": "détourné", "description": ""},
        )
        self.assertEqual(response.status_code, 404)
        self.bob_project.refresh_from_db()
        self.assertEqual(self.bob_project.name, "Projet Bob")

    def test_cannot_delete_other_users_project_via_post(self):
        response = self.client.post(
            reverse("project_delete", args=[self.bob_project.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=self.bob_project.pk).exists())

    def test_anonymous_is_redirected_on_every_view(self):
        self.client.logout()
        urls = [
            reverse("project_list"),
            reverse("project_create"),
            reverse("project_detail", args=[self.alice_project.pk]),
            reverse("project_update", args=[self.alice_project.pk]),
            reverse("project_delete", args=[self.alice_project.pk]),
        ]
        for url in urls:
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    # 302 vers la connexion, jamais 500.
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(reverse("login"), response.url)
        # Aucune écriture n'a eu lieu au passage.
        self.assertTrue(Project.objects.filter(pk=self.alice_project.pk).exists())

    # --- Création ---

    def test_create_sets_owner_to_current_user(self):
        response = self.client.post(
            reverse("project_create"), {"name": "Nouveau", "description": "x"}
        )
        self.assertRedirects(response, reverse("project_list"))
        project = Project.objects.get(name="Nouveau")
        self.assertEqual(project.owner, self.alice)

    def test_owner_in_post_is_ignored(self):
        self.client.post(
            reverse("project_create"),
            {"name": "Nouveau", "description": "", "owner": self.bob.pk},
        )
        self.assertEqual(Project.objects.get(name="Nouveau").owner, self.alice)

    def test_empty_name_shows_error_in_html(self):
        response = self.client.post(
            reverse("project_create"), {"name": "", "description": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        # L'erreur doit être visible, pas seulement présente dans form.errors.
        self.assertContains(response, "text-error")
        self.assertEqual(Project.objects.filter(owner=self.alice).count(), 1)

    def test_name_too_long_rejected(self):
        response = self.client.post(
            reverse("project_create"), {"name": "x" * 201, "description": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)

    # --- Unicité (owner, name) : le piège de cette tranche ---

    def test_duplicate_name_shows_form_error_not_500(self):
        # Sans clean_name(), Django exclurait owner de validate_unique() : le
        # doublon passerait la validation et exploserait à l'INSERT en 500.
        response = self.client.post(
            reverse("project_create"),
            {"name": "Projet Alice", "description": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        # Le message réel, pas juste une classe CSS : documente le comportement
        # et ne passerait pas si l'erreur venait d'un autre champ.
        self.assertContains(response, "Vous avez déjà un projet portant ce nom.")
        self.assertEqual(Project.objects.filter(owner=self.alice).count(), 1)

    def test_same_name_allowed_for_another_user(self):
        # « Projet Bob » appartient à Bob : Alice doit pouvoir l'utiliser.
        response = self.client.post(
            reverse("project_create"), {"name": "Projet Bob", "description": ""}
        )
        self.assertRedirects(response, reverse("project_list"))
        self.assertTrue(
            Project.objects.filter(owner=self.alice, name="Projet Bob").exists()
        )

    def test_update_keeping_same_name(self):
        response = self.client.post(
            reverse("project_update", args=[self.alice_project.pk]),
            {"name": "Projet Alice", "description": "maj"},
        )
        self.assertRedirects(response, reverse("project_list"))
        self.alice_project.refresh_from_db()
        self.assertEqual(self.alice_project.description, "maj")

    def test_update_to_another_own_project_name_rejected(self):
        other = Project.objects.create(owner=self.alice, name="Autre")
        response = self.client.post(
            reverse("project_update", args=[other.pk]),
            {"name": "Projet Alice", "description": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        other.refresh_from_db()
        self.assertEqual(other.name, "Autre")

    # --- Suppression ---

    def test_get_delete_shows_confirmation_without_deleting(self):
        response = self.client.get(
            reverse("project_delete", args=[self.alice_project.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Project.objects.filter(pk=self.alice_project.pk).exists())

    def test_post_delete_removes_project_and_cascades_tasks(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        bob_task = Task.objects.create(title="T Bob", project=self.bob_project)
        response = self.client.post(
            reverse("project_delete", args=[self.alice_project.pk])
        )
        self.assertRedirects(response, reverse("project_list"))
        self.assertFalse(Project.objects.filter(pk=self.alice_project.pk).exists())
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())
        # Les tâches des autres projets ne sont pas touchées.
        self.assertTrue(Task.objects.filter(pk=bob_task.pk).exists())

    def test_delete_confirmation_shows_task_count(self):
        Task.objects.create(title="T1", project=self.alice_project)
        Task.objects.create(title="T2", project=self.alice_project)
        response = self.client.get(
            reverse("project_delete", args=[self.alice_project.pk])
        )
        self.assertEqual(response.context["task_count"], 2)
        # Le compte et son pluriel doivent apparaître dans la page, pas
        # seulement dans le contexte.
        self.assertContains(response, "2")
        self.assertContains(response, "seront")

    def test_list_displays_task_count(self):
        # Si annotate() disparaissait, task_count deviendrait une variable
        # manquante : Django la rendrait par une chaîne vide, sans erreur et
        # sans changer le nombre de requêtes. Ce test est le seul garde-fou.
        Task.objects.create(title="T1", project=self.alice_project)
        Task.objects.create(title="T2", project=self.alice_project)
        Task.objects.create(title="T3", project=self.alice_project)
        response = self.client.get(reverse("project_list"))
        # Le compteur de tâches apparaît dans la carte du projet.
        self.assertContains(response, "3 tâches")

    # --- Performance ---

    def test_list_query_count_does_not_grow_with_projects(self):
        # On compare à une référence mesurée plutôt qu'à un nombre en dur :
        # ce qui compte, c'est que le total n'augmente pas avec les projets.
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(reverse("project_list"))
        for i in range(10):
            Project.objects.create(owner=self.alice, name=f"Projet {i}")
        with self.assertNumQueries(len(baseline)):
            self.client.get(reverse("project_list"))
