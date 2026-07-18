from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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
