from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from projects.models import Project
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Task

User = get_user_model()


class TaskAPITestCase(APITestCase):
    """Tests de la ressource Task (cf. tasks/SPEC.md)."""

    def setUp(self):
        # L'email est unique en base (cf. accounts/SPEC.md) : chaque utilisateur
        # de test doit donc avoir le sien.
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.alice_project = Project.objects.create(
            owner=self.alice, name="Projet Alice"
        )
        self.bob_project = Project.objects.create(
            owner=self.bob, name="Projet Bob"
        )
        self.list_url = reverse("task-list")

    def detail_url(self, pk):
        return reverse("task-detail", args=[pk])

    # --- Cas nominal (CRUD) ---

    def test_create_task(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "Rédiger la maquette", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Rédiger la maquette")
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.project, self.alice_project)

    def test_list_only_own_tasks(self):
        Task.objects.create(title="T Alice", project=self.alice_project)
        Task.objects.create(title="T Bob", project=self.bob_project)
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "T Alice")

    def test_retrieve_own_task(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(task.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "T1")

    def test_update_own_task(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            self.detail_url(task.pk),
            {
                "title": "T1 modifiée",
                "status": Task.Status.IN_PROGRESS,
                "priority": Task.Priority.HIGH,
                "project": self.alice_project.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.title, "T1 modifiée")
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
        self.assertEqual(task.priority, Task.Priority.HIGH)

    def test_partial_update_own_task(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(task.pk),
            {"status": Task.Status.DONE},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_delete_own_task(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        response = self.client.delete(self.detail_url(task.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    # --- Cas limites : title ---

    def test_create_empty_title(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_title(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"project": self.alice_project.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_title_too_long(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "x" * 201, "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Cas limites : project ---

    def test_create_missing_project(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"title": "T1"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_nonexistent_project(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url, {"title": "T1", "project": 999999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_other_users_project(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "T1", "project": self.bob_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Task.objects.filter(project=self.bob_project).exists())

    def test_other_users_project_indistinguishable_from_nonexistent(self):
        # SPEC §5 : « projet d'autrui » et « projet inexistant » doivent produire
        # exactement le même corps de réponse. On interroge le MÊME pk dans les
        # deux cas (en supprimant le projet entre les deux), sans quoi le pk
        # interpolé dans le message rendrait l'égalité stricte impossible et la
        # comparaison ne prouverait rien.
        self.client.force_authenticate(self.alice)
        pk = self.bob_project.pk

        other_users = self.client.post(
            self.list_url, {"title": "T1", "project": pk}, format="json"
        )
        self.bob_project.delete()
        nonexistent = self.client.post(
            self.list_url, {"title": "T1", "project": pk}, format="json"
        )

        self.assertEqual(other_users.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nonexistent.status_code, status.HTTP_400_BAD_REQUEST)
        # L'erreur porte bien sur `project` : sans cette assertion, deux 400
        # génériques identiques passeraient aussi.
        self.assertIn("project", other_users.data)
        self.assertEqual(other_users.data, nonexistent.data)

    def test_indistinguishable_on_update_too(self):
        # SPEC §4 : la restriction vaut aussi en update/PATCH, pas seulement en
        # create. Même protocole, à pk identique.
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        pk = self.bob_project.pk

        other_users = self.client.patch(
            self.detail_url(task.pk), {"project": pk}, format="json"
        )
        self.bob_project.delete()
        nonexistent = self.client.patch(
            self.detail_url(task.pk), {"project": pk}, format="json"
        )

        self.assertEqual(other_users.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nonexistent.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project", other_users.data)
        self.assertEqual(other_users.data, nonexistent.data)

    def test_cannot_move_task_to_other_users_project(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(task.pk),
            {"project": self.bob_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        task.refresh_from_db()
        self.assertEqual(task.project, self.alice_project)

    # --- Cas limites : choices ---

    def test_create_invalid_status(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "T1", "project": self.alice_project.pk, "status": "fini"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_accented_status_rejected(self):
        # Les valeurs stockées sont en ASCII sans accents : "terminé" doit être
        # rejeté, seul "termine" est valide.
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {
                "title": "T1",
                "project": self.alice_project.pk,
                "status": "terminé",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_priority(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {
                "title": "T1",
                "project": self.alice_project.pk,
                "priority": "urgente",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_defaults_applied_when_status_and_priority_absent(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "T1", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Task.Status.TODO)
        self.assertEqual(response.data["priority"], Task.Priority.MEDIUM)

    # --- Cas limites : description & due_date ---

    def test_create_without_description(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "T1", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["description"], "")

    def test_create_without_due_date(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {"title": "T1", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["due_date"])

    def test_create_malformed_due_date(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {
                "title": "T1",
                "project": self.alice_project.pk,
                "due_date": "01/08/2026",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_past_due_date_allowed(self):
        # Une échéance passée est autorisée : c'est ce qui rend une tâche
        # « en retard » au tableau de bord.
        past = date.today() - timedelta(days=7)
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.list_url,
            {
                "title": "T1",
                "project": self.alice_project.pk,
                "due_date": past.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["due_date"], past.isoformat())

    # --- Permissions / isolation par utilisateur ---

    def test_cannot_retrieve_other_users_task(self):
        task = Task.objects.create(title="T Bob", project=self.bob_project)
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.detail_url(task.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_users_task(self):
        task = Task.objects.create(title="T Bob", project=self.bob_project)
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            self.detail_url(task.pk),
            {"title": "hack", "project": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_patch_other_users_task(self):
        task = Task.objects.create(title="T Bob", project=self.bob_project)
        self.client.force_authenticate(self.alice)
        response = self.client.patch(
            self.detail_url(task.pk), {"title": "hack"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_task(self):
        task = Task.objects.create(title="T Bob", project=self.bob_project)
        self.client.force_authenticate(self.alice)
        response = self.client.delete(self.detail_url(task.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Cascade ---

    def test_deleting_project_deletes_its_tasks(self):
        task = Task.objects.create(title="T1", project=self.alice_project)
        other_task = Task.objects.create(title="T Bob", project=self.bob_project)
        self.alice_project.delete()
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())
        self.assertTrue(Task.objects.filter(pk=other_task.pk).exists())


class TaskFilterTestCase(APITestCase):
    """Tests des filtres de la liste des tâches (cf. tasks/SPEC-filters.md)."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.project_a = Project.objects.create(owner=self.alice, name="Projet A")
        self.project_b = Project.objects.create(owner=self.alice, name="Projet B")
        self.bob_project = Project.objects.create(owner=self.bob, name="Projet Bob")

        # Tâches d'Alice, variées, pour discriminer les filtres.
        self.t_todo_high = Task.objects.create(
            title="À faire / haute",
            project=self.project_a,
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
            due_date=date(2026, 1, 10),
        )
        self.t_done_low = Task.objects.create(
            title="Terminé / basse",
            project=self.project_a,
            status=Task.Status.DONE,
            priority=Task.Priority.LOW,
            due_date=date(2026, 6, 15),
        )
        self.t_inprog_b = Task.objects.create(
            title="En cours / projet B",
            project=self.project_b,
            status=Task.Status.IN_PROGRESS,
            priority=Task.Priority.MEDIUM,
            due_date=None,
        )
        # Tâche de Bob : ne doit jamais apparaître pour Alice.
        self.bob_task = Task.objects.create(
            title="Tâche de Bob",
            project=self.bob_project,
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
        )
        self.list_url = reverse("task-list")
        self.client.force_authenticate(self.alice)

    def ids(self, response):
        return {task["id"] for task in response.data}

    # --- Chaque filtre isolément ---

    def test_no_filter_returns_all_own_tasks(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.ids(response),
            {self.t_todo_high.pk, self.t_done_low.pk, self.t_inprog_b.pk},
        )

    def test_filter_by_status(self):
        response = self.client.get(self.list_url, {"status": Task.Status.DONE})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_done_low.pk})

    def test_filter_by_priority(self):
        response = self.client.get(
            self.list_url, {"priority": Task.Priority.HIGH}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_todo_high.pk})

    def test_filter_by_project(self):
        response = self.client.get(self.list_url, {"project": self.project_b.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_inprog_b.pk})

    def test_filter_due_date_before(self):
        # Inclut la borne ; exclut les due_date null.
        response = self.client.get(
            self.list_url, {"due_date_before": "2026-01-10"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_todo_high.pk})

    def test_filter_due_date_after(self):
        response = self.client.get(
            self.list_url, {"due_date_after": "2026-02-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_done_low.pk})

    # --- Combinaison (ET) ---

    def test_combined_filters_are_intersected(self):
        # project_a a une tâche TODO/haute et une DONE/basse ; en croisant
        # project=A et priority=basse, on n'attend que la seconde.
        response = self.client.get(
            self.list_url,
            {"project": self.project_a.pk, "priority": Task.Priority.LOW},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_done_low.pk})

    def test_due_date_range_both_bounds(self):
        response = self.client.get(
            self.list_url,
            {"due_date_after": "2026-01-01", "due_date_before": "2026-03-01"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.t_todo_high.pk})

    # --- Valeurs invalides ---

    def test_invalid_status_returns_400(self):
        response = self.client.get(self.list_url, {"status": "fini"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_priority_returns_400(self):
        response = self.client.get(self.list_url, {"priority": "urgente"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_due_date_returns_400(self):
        # Django accepte plusieurs formats de date (DATE_INPUT_FORMATS), donc on
        # utilise une valeur réellement impossible à parser.
        response = self.client.get(
            self.list_url, {"due_date_before": "pas-une-date"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Sécurité : le filtre ne peut pas franchir l'isolation utilisateur ---

    def test_filter_by_other_users_project_returns_empty(self):
        response = self.client.get(
            self.list_url, {"project": self.bob_project.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_filter_by_nonexistent_project_returns_empty(self):
        # SPEC §4 : « projet inexistant » et « projet d'autrui » doivent donner
        # le MÊME résultat (200 []). Une réponse 400 pour l'un et 200 pour
        # l'autre serait un oracle révélant l'existence des projets d'autrui.
        response = self.client.get(self.list_url, {"project": 999999})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_non_numeric_project_returns_400(self):
        response = self.client.get(self.list_url, {"project": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filters_never_leak_other_users_tasks(self):
        # Le statut de la tâche de Bob (TODO) matche des tâches d'Alice, mais
        # jamais la sienne ne doit apparaître.
        response = self.client.get(self.list_url, {"status": Task.Status.TODO})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.bob_task.pk, self.ids(response))
        self.assertEqual(self.ids(response), {self.t_todo_high.pk})


class DashboardTestCase(APITestCase):
    """Tests du tableau de bord (cf. tasks/SPEC-dashboard.md)."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.project = Project.objects.create(owner=self.alice, name="Projet A")
        self.bob_project = Project.objects.create(owner=self.bob, name="Projet Bob")
        self.url = reverse("dashboard")
        # Même source que la vue (timezone.localdate) pour éviter tout écart de
        # date près de minuit selon le fuseau.
        self.today = timezone.localdate()
        self.client.force_authenticate(self.alice)

    def make_task(self, owner_project, days_offset=None, status_value=None):
        due = None if days_offset is None else self.today + timedelta(days=days_offset)
        return Task.objects.create(
            title="T",
            project=owner_project,
            due_date=due,
            status=status_value or Task.Status.TODO,
        )

    def ids(self, section):
        return {task["id"] for task in section["tasks"]}

    # --- Catégorisation ---

    def test_overdue_contains_past_unfinished_tasks(self):
        overdue = self.make_task(self.project, days_offset=-3)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overdue"]["count"], 1)
        self.assertEqual(self.ids(response.data["overdue"]), {overdue.pk})
        # Les tâches des listes exposent les mêmes champs que /api/tasks/
        # (SPEC §4 : sérialisées par TaskSerializer).
        self.assertEqual(
            set(response.data["overdue"]["tasks"][0]),
            {
                "id", "title", "description", "status", "priority",
                "due_date", "project", "created_at", "updated_at",
            },
        )

    def test_task_due_today_is_upcoming_not_overdue(self):
        today_task = self.make_task(self.project, days_offset=0)
        response = self.client.get(self.url)
        self.assertEqual(self.ids(response.data["upcoming"]), {today_task.pk})
        self.assertEqual(response.data["overdue"]["count"], 0)

    def test_task_at_14_day_boundary_is_upcoming(self):
        boundary = self.make_task(self.project, days_offset=14)
        response = self.client.get(self.url)
        self.assertIn(boundary.pk, self.ids(response.data["upcoming"]))

    def test_task_beyond_14_days_is_not_upcoming(self):
        self.make_task(self.project, days_offset=15)
        response = self.client.get(self.url)
        self.assertEqual(response.data["upcoming"]["count"], 0)

    def test_overdue_but_done_is_excluded(self):
        # En retard sur la date, mais terminée : ne compte pas comme en retard,
        # mais reste comptée dans by_status.
        self.make_task(self.project, days_offset=-3, status_value=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(response.data["overdue"]["count"], 0)
        self.assertEqual(response.data["by_status"][Task.Status.DONE], 1)

    def test_upcoming_but_done_is_excluded(self):
        self.make_task(self.project, days_offset=5, status_value=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(response.data["upcoming"]["count"], 0)

    def test_task_without_due_date_is_neither_overdue_nor_upcoming(self):
        undated = self.make_task(self.project, days_offset=None)
        response = self.client.get(self.url)
        self.assertEqual(response.data["overdue"]["count"], 0)
        self.assertEqual(response.data["upcoming"]["count"], 0)
        # ... mais bien comptée dans by_status.
        self.assertEqual(response.data["by_status"][Task.Status.TODO], 1)
        self.assertTrue(Task.objects.filter(pk=undated.pk).exists())

    # --- by_status ---

    def test_by_status_counts_all_statuses(self):
        self.make_task(self.project, status_value=Task.Status.TODO)
        self.make_task(self.project, status_value=Task.Status.TODO)
        self.make_task(self.project, status_value=Task.Status.IN_PROGRESS)
        self.make_task(self.project, status_value=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(
            response.data["by_status"],
            {
                Task.Status.TODO: 2,
                Task.Status.IN_PROGRESS: 1,
                Task.Status.DONE: 1,
            },
        )

    def test_empty_dashboard_for_user_without_tasks(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overdue"], {"count": 0, "tasks": []})
        self.assertEqual(response.data["upcoming"], {"count": 0, "tasks": []})
        self.assertEqual(
            response.data["by_status"],
            {Task.Status.TODO: 0, Task.Status.IN_PROGRESS: 0, Task.Status.DONE: 0},
        )

    # --- Sécurité ---

    def test_dashboard_isolates_other_users_tasks(self):
        # Tâches de Bob dans toutes les catégories : ne doivent jamais compter.
        self.make_task(self.bob_project, days_offset=-3)  # en retard
        self.make_task(self.bob_project, days_offset=5)  # à venir
        self.make_task(self.bob_project, status_value=Task.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(response.data["overdue"]["count"], 0)
        self.assertEqual(response.data["upcoming"]["count"], 0)
        self.assertEqual(
            response.data["by_status"],
            {Task.Status.TODO: 0, Task.Status.IN_PROGRESS: 0, Task.Status.DONE: 0},
        )

    def test_unauthenticated_request_rejected(self):
        self.client.force_authenticate(None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TaskFrontTestCase(TestCase):
    """Tests du CRUD tâches côté front (cf. tasks/SPEC-front.md)."""

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
        self.task = Task.objects.create(title="T1", project=self.project)
        self.detail_url = reverse("project_detail", args=[self.project.pk])
        self.create_url = reverse("task_create", kwargs={"project_pk": self.project.pk})
        self.client.force_login(self.alice)

    # --- Isolation ---

    def test_create_in_other_users_project_returns_404(self):
        url = reverse("task_create", kwargs={"project_pk": self.bob_project.pk})
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    url, {"title": "X", "status": Task.Status.TODO, "priority": Task.Priority.MEDIUM}
                )
                self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.filter(project=self.bob_project).exists())

    def test_modify_or_delete_other_users_task_returns_404(self):
        bob_task = Task.objects.create(title="T Bob", project=self.bob_project)
        cases = [
            ("get", reverse("task_update", args=[bob_task.pk])),
            ("post", reverse("task_update", args=[bob_task.pk])),
            ("get", reverse("task_delete", args=[bob_task.pk])),
            ("post", reverse("task_delete", args=[bob_task.pk])),
        ]
        for method, url in cases:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=bob_task.pk).exists())

    def test_anonymous_is_redirected_on_every_view(self):
        self.client.logout()
        urls = [
            self.create_url,
            reverse("task_update", args=[self.task.pk]),
            reverse("task_delete", args=[self.task.pk]),
        ]
        for url in urls:
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    # 302 vers la connexion, jamais 404 (le projet parent ne
                    # doit pas être chargé avant l'authentification) ni 500.
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(reverse("login"), response.url)

    # --- Création ---

    def valid_payload(self, **overrides):
        data = {
            "title": "Nouvelle tâche",
            "description": "",
            "status": Task.Status.IN_PROGRESS,
            "priority": Task.Priority.HIGH,
            "due_date": "",
        }
        data.update(overrides)
        return data

    def test_create_attaches_task_to_url_project(self):
        response = self.client.post(self.create_url, self.valid_payload())
        self.assertRedirects(response, self.detail_url)
        task = Task.objects.get(title="Nouvelle tâche")
        self.assertEqual(task.project, self.project)

    def test_create_form_preselects_defaults(self):
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form["status"].value(), Task.Status.TODO)
        self.assertEqual(form["priority"].value(), Task.Priority.MEDIUM)

    def test_empty_title_shows_error_in_html(self):
        response = self.client.post(self.create_url, self.valid_payload(title=""))
        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["form"].errors)
        # Le message d'erreur réel doit être rendu, pas seulement la classe CSS.
        self.assertContains(response, "Ce champ est obligatoire.")
        self.assertEqual(Task.objects.filter(project=self.project).count(), 1)

    def test_invalid_status_rejected(self):
        response = self.client.post(self.create_url, self.valid_payload(status="fini"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)

    def test_invalid_priority_rejected(self):
        response = self.client.post(
            self.create_url, self.valid_payload(priority="urgente")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("priority", response.context["form"].errors)

    def test_create_shows_success_message(self):
        response = self.client.post(
            self.create_url, self.valid_payload(), follow=True
        )
        self.assertContains(response, "Tâche créée.")

    def test_missing_status_is_form_error_not_silent_default(self):
        payload = self.valid_payload()
        del payload["status"]
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)

    def test_project_in_post_is_ignored(self):
        self.client.post(
            self.create_url, self.valid_payload(project=self.bob_project.pk)
        )
        task = Task.objects.get(title="Nouvelle tâche")
        self.assertEqual(task.project, self.project)

    # --- due_date : entrée ET sortie (le piège fr-fr) ---

    def test_due_date_iso_format_is_accepted(self):
        response = self.client.post(
            self.create_url, self.valid_payload(due_date="2026-08-01")
        )
        self.assertRedirects(response, self.detail_url)
        task = Task.objects.get(title="Nouvelle tâche")
        self.assertEqual(task.due_date, date(2026, 8, 1))

    def test_empty_due_date_is_null(self):
        self.client.post(self.create_url, self.valid_payload(due_date=""))
        self.assertIsNone(Task.objects.get(title="Nouvelle tâche").due_date)

    def test_past_due_date_is_allowed(self):
        past = (date.today() - timedelta(days=7)).isoformat()
        response = self.client.post(
            self.create_url, self.valid_payload(due_date=past)
        )
        self.assertRedirects(response, self.detail_url)

    def test_edit_form_redisplays_date_in_iso_format(self):
        # Sans format="%Y-%m-%d" sur le widget, la date se rendrait en JJ/MM/AAAA
        # → invalide pour <input type=date>, qui s'ouvrirait vide.
        self.task.due_date = date(2026, 8, 1)
        self.task.save()
        response = self.client.get(reverse("task_update", args=[self.task.pk]))
        self.assertContains(response, 'value="2026-08-01"')

    # --- Modification ---

    def test_update_changes_fields_but_not_project(self):
        response = self.client.post(
            reverse("task_update", args=[self.task.pk]),
            self.valid_payload(title="T1 modifiée", status=Task.Status.DONE),
        )
        self.assertRedirects(response, self.detail_url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "T1 modifiée")
        self.assertEqual(self.task.status, Task.Status.DONE)
        self.assertEqual(self.task.project, self.project)

    # --- Suppression ---

    def test_get_delete_shows_confirmation_without_deleting(self):
        response = self.client.get(reverse("task_delete", args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_post_delete_removes_task_and_keeps_project(self):
        response = self.client.post(reverse("task_delete", args=[self.task.pk]))
        self.assertRedirects(response, self.detail_url)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    # --- Affichage & performance de la liste (dans le détail projet) ---

    def test_detail_lists_project_tasks(self):
        Task.objects.create(
            title="À faire haute",
            project=self.project,
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
        )
        response = self.client.get(self.detail_url)
        self.assertContains(response, "À faire haute")
        # Libellés accentués via get_*_display, pas les valeurs ASCII.
        self.assertContains(response, "Haute")

    def test_detail_task_list_query_count_is_constant(self):
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(self.detail_url)
        for i in range(10):
            Task.objects.create(title=f"T{i}", project=self.project)
        with self.assertNumQueries(len(baseline)):
            self.client.get(self.detail_url)


class TaskListFrontTestCase(TestCase):
    """Tests de la liste filtrable des tâches (cf. tasks/SPEC-front-filters.md)."""

    PASSWORD = "Brouillard-Tuile-42"

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=self.PASSWORD
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password=self.PASSWORD
        )
        self.project_a = Project.objects.create(owner=self.alice, name="Projet A")
        self.project_b = Project.objects.create(owner=self.alice, name="Projet B")
        self.bob_project = Project.objects.create(owner=self.bob, name="Projet Bob")

        self.t_a_todo_high = Task.objects.create(
            title="A / à faire / haute",
            project=self.project_a,
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
            due_date=date(2026, 1, 10),
        )
        self.t_a_done_low = Task.objects.create(
            title="A / terminé / basse",
            project=self.project_a,
            status=Task.Status.DONE,
            priority=Task.Priority.LOW,
            due_date=date(2026, 6, 15),
        )
        self.t_b_inprog = Task.objects.create(
            title="B / en cours",
            project=self.project_b,
            status=Task.Status.IN_PROGRESS,
            priority=Task.Priority.MEDIUM,
        )
        self.bob_task = Task.objects.create(
            title="Tâche de Bob", project=self.bob_project
        )
        self.url = reverse("task_list")
        self.client.force_login(self.alice)

    def titles(self, response):
        return {t.title for t in response.context["tasks"]}

    # --- Base / isolation ---

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_no_filter_lists_all_own_tasks(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.titles(response),
            {"A / à faire / haute", "A / terminé / basse", "B / en cours"},
        )
        self.assertNotIn("Tâche de Bob", self.titles(response))

    def test_project_select_only_lists_own_projects(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Projet A")
        self.assertContains(response, "Projet B")
        self.assertNotContains(response, "Projet Bob")

    def test_isolation_never_shows_other_users_tasks(self):
        # Un statut que possède aussi Bob ne fait pas apparaître sa tâche.
        response = self.client.get(self.url, {"status": Task.Status.TODO})
        self.assertNotIn("Tâche de Bob", self.titles(response))

    # --- Filtres ---

    def test_filter_by_project(self):
        response = self.client.get(self.url, {"project": self.project_b.pk})
        self.assertEqual(self.titles(response), {"B / en cours"})

    def test_filter_by_status(self):
        response = self.client.get(self.url, {"status": Task.Status.DONE})
        self.assertEqual(self.titles(response), {"A / terminé / basse"})

    def test_filter_by_priority(self):
        response = self.client.get(self.url, {"priority": Task.Priority.HIGH})
        self.assertEqual(self.titles(response), {"A / à faire / haute"})

    def test_filter_due_date_after(self):
        response = self.client.get(self.url, {"due_date_after": "2026-03-01"})
        self.assertEqual(self.titles(response), {"A / terminé / basse"})

    def test_filter_due_date_before(self):
        response = self.client.get(self.url, {"due_date_before": "2026-01-10"})
        self.assertEqual(self.titles(response), {"A / à faire / haute"})

    def test_combined_filters_are_intersected(self):
        response = self.client.get(
            self.url,
            {"project": self.project_a.pk, "priority": Task.Priority.LOW},
        )
        self.assertEqual(self.titles(response), {"A / terminé / basse"})

    # --- Persistance du formulaire ---

    def test_selected_filters_persist_in_form(self):
        response = self.client.get(
            self.url,
            {"status": Task.Status.DONE, "due_date_after": "2026-03-01"},
        )
        # Le <select> statut ré-affiche l'option choisie (assertInHTML normalise
        # les espaces), et la date se ré-affiche en ISO (piège tranche 3 évité).
        self.assertInHTML(
            '<option value="termine" selected>Terminé</option>',
            response.content.decode(),
        )
        self.assertContains(response, 'value="2026-03-01"')

    # --- Valeurs invalides forgées : 200, jamais 500 (décision SPEC §7) ---

    def test_invalid_status_is_ignored_not_500(self):
        response = self.client.get(self.url, {"status": "bidon"})
        self.assertEqual(response.status_code, 200)
        # Filtre ignoré → toutes les tâches du user.
        self.assertEqual(len(response.context["tasks"]), 3)

    def test_malformed_date_is_ignored_not_500(self):
        response = self.client.get(self.url, {"due_date_before": "pas-une-date"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["tasks"]), 3)

    def test_non_numeric_project_is_ignored_not_500(self):
        response = self.client.get(self.url, {"project": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["tasks"]), 3)

    def test_other_users_project_pk_returns_empty(self):
        response = self.client.get(self.url, {"project": self.bob_project.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["tasks"]), [])

    # --- États vides distincts (SPEC §8) ---

    def test_empty_state_without_tasks(self):
        Task.objects.filter(project__owner=self.alice).delete()
        response = self.client.get(self.url)
        self.assertFalse(response.context["has_filters"])
        self.assertContains(response, "Vous n'avez pas encore de tâche.")

    def test_empty_state_with_filters_but_no_match(self):
        # L'utilisateur a des tâches, mais aucune priorité « haute » terminée.
        response = self.client.get(
            self.url,
            {"status": Task.Status.TODO, "priority": Task.Priority.LOW},
        )
        self.assertEqual(list(response.context["tasks"]), [])
        self.assertTrue(response.context["has_filters"])
        self.assertContains(response, "Aucune tâche ne correspond à ces filtres.")

    # --- Performance ---

    def test_query_count_is_constant(self):
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(self.url)
        for i in range(10):
            Task.objects.create(title=f"Extra {i}", project=self.project_a)
        with self.assertNumQueries(len(baseline)):
            self.client.get(self.url)


class PolishTestCase(TestCase):
    """Tests du polish visuel (cf. core/SPEC-front-polish.md).

    Présentation : on vérifie les classes CSS rendues et le helper is_overdue.
    """

    PASSWORD = "Brouillard-Tuile-42"

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password=self.PASSWORD
        )
        self.project = Project.objects.create(owner=self.user, name="Projet")
        self.today = timezone.localdate()
        self.list_url = reverse("task_list")
        self.client.force_login(self.user)

    # --- is_overdue (helper) ---

    def test_is_overdue_filter(self):
        from tasks.templatetags.task_badges import is_overdue

        overdue = Task.objects.create(
            title="R", project=self.project, status=Task.Status.TODO,
            due_date=self.today - timedelta(days=1),
        )
        future = Task.objects.create(
            title="F", project=self.project, status=Task.Status.TODO,
            due_date=self.today + timedelta(days=1),
        )
        done_past = Task.objects.create(
            title="D", project=self.project, status=Task.Status.DONE,
            due_date=self.today - timedelta(days=5),
        )
        no_date = Task.objects.create(title="N", project=self.project)
        self.assertTrue(is_overdue(overdue))
        self.assertFalse(is_overdue(future))
        # Terminée : pas « en retard » même si l'échéance est passée.
        self.assertFalse(is_overdue(done_past))
        self.assertFalse(is_overdue(no_date))

    # --- Badges ---

    def test_status_and_priority_badges_colors(self):
        Task.objects.create(
            title="T", project=self.project,
            status=Task.Status.DONE, priority=Task.Priority.HIGH,
        )
        response = self.client.get(self.list_url)
        # Terminé → vert, Haute → rouge, libellés accentués conservés.
        self.assertContains(response, "text-bg-success")
        self.assertContains(response, "text-bg-danger")
        self.assertContains(response, "Terminé")
        self.assertContains(response, "Haute")

    def test_overdue_date_is_highlighted(self):
        Task.objects.create(
            title="Retard", project=self.project, status=Task.Status.TODO,
            due_date=self.today - timedelta(days=2),
        )
        response = self.client.get(self.list_url)
        self.assertContains(response, "text-danger fw-semibold")

    def test_future_task_date_not_highlighted(self):
        Task.objects.create(
            title="Futur", project=self.project, status=Task.Status.TODO,
            due_date=self.today + timedelta(days=5),
        )
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "text-danger fw-semibold")

    # --- Navigation active ---

    def test_nav_highlights_current_section(self):
        # assertInHTML normalise les espaces (l'attribut class et href sont sur
        # des lignes différentes dans le template).
        on_tasks = self.client.get(self.list_url).content.decode()
        self.assertInHTML(
            '<a class="nav-link active" href="/taches/">Tâches</a>', on_tasks
        )
        on_projects = self.client.get(reverse("project_list")).content.decode()
        self.assertInHTML(
            '<a class="nav-link active" href="/projets/">Projets</a>', on_projects
        )

    def test_nav_task_create_is_not_double_active(self):
        # /projets/<pk>/taches/nouvelle/ contient « projets » ET « taches » dans
        # le chemin : le repère par nom d'URL évite d'allumer les deux liens.
        url = reverse("task_create", kwargs={"project_pk": self.project.pk})
        html = self.client.get(url).content.decode()
        # Un seul lien de nav actif, et c'est « Tâches ».
        self.assertEqual(html.count("nav-link active"), 1)
        self.assertInHTML(
            '<a class="nav-link active" href="/taches/">Tâches</a>', html
        )

    def test_badge_does_not_crash_on_unknown_value(self):
        from tasks.templatetags.task_badges import priority_badge, status_badge

        # Une valeur hors choix ne doit pas lever (helper d'affichage).
        self.assertEqual(status_badge("inconnu")["css"], "secondary")
        self.assertEqual(status_badge("inconnu")["label"], "inconnu")
        self.assertEqual(priority_badge("???")["css"], "secondary")

    # --- État vide soigné ---

    def test_empty_task_list_shows_styled_block_not_table(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, "Vous n'avez pas encore de tâche.")
        # Encart centré, et pas d'en-tête de tableau vide.
        self.assertContains(response, "text-center text-muted")
        self.assertNotContains(response, "<th>Titre</th>")


class AIAssistantTestCase(APITestCase):
    """Tests de l'assistant IA (cf. tasks/SPEC-ai-assistant.md §8).

    L'appel OpenAI est TOUJOURS mocké au niveau du client (`tasks.ai.OpenAI`) :
    on exerce le vrai code de parsing/normalisation sans jamais toucher à l'API
    réelle.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.alice_project = Project.objects.create(
            owner=self.alice, name="Projet Alice"
        )
        self.bob_project = Project.objects.create(
            owner=self.bob, name="Projet Bob"
        )
        self.generate_url = reverse("task_generate")
        self.confirm_url = reverse("task_confirm")

    def _openai_returning(self, content):
        """Mock du client OpenAI dont la complétion renvoie `content` (texte)."""
        from unittest.mock import MagicMock

        message = MagicMock()
        message.content = content
        choice = MagicMock()
        choice.message = message
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        return client

    def _openai_raising(self, exc):
        """Mock du client OpenAI dont la complétion lève `exc`."""
        from unittest.mock import MagicMock

        client = MagicMock()
        client.chat.completions.create.side_effect = exc
        return client

    # --- generate ---

    def test_generate_valid_returns_tasks_without_creating(self):
        import json
        from unittest.mock import patch

        content = json.dumps(
            {
                "tasks": [
                    {
                        "title": "Réserver la salle",
                        "description": "Pour la réunion",
                        "priority": "haute",
                        "status": "a_faire",
                        "due_date": "2026-08-15",
                    }
                ]
            }
        )
        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI", return_value=self._openai_returning(content)
        ):
            response = self.client.post(
                self.generate_url,
                {"text": "Réserver la salle en priorité", "project_id": self.alice_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["tasks"]), 1)
        self.assertEqual(response.data["tasks"][0]["title"], "Réserver la salle")
        # Rien ne doit être créé en base à l'étape d'aperçu.
        self.assertEqual(Task.objects.count(), 0)

    def test_generate_normalizes_out_of_choices_values(self):
        """Décision §5 : valeurs hors-choices normalisées au défaut, pas rejetées."""
        import json
        from unittest.mock import patch

        content = json.dumps(
            {
                "tasks": [
                    {
                        "title": "Tâche bancale",
                        "priority": "urgente",  # invalide → moyenne
                        "status": "bloque",  # invalide → a_faire
                        "due_date": "",  # vide → null
                    }
                ]
            }
        )
        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI", return_value=self._openai_returning(content)
        ):
            response = self.client.post(
                self.generate_url,
                {"text": "peu importe", "project_id": self.alice_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task = response.data["tasks"][0]
        self.assertEqual(task["priority"], Task.Priority.MEDIUM)
        self.assertEqual(task["status"], Task.Status.TODO)
        self.assertIsNone(task["due_date"])

    def test_generate_project_of_another_user_returns_404(self):
        from unittest.mock import patch

        self.client.force_authenticate(self.alice)
        # Le mock est en place mais ne doit même pas être appelé : le 404 tombe
        # avant tout appel externe.
        with patch(
            "tasks.ai.OpenAI", return_value=self._openai_returning("{}")
        ) as mocked:
            response = self.client.post(
                self.generate_url,
                {"text": "quelque chose", "project_id": self.bob_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Task.objects.count(), 0)
        mocked.assert_not_called()

    def test_generate_unparseable_response_returns_400(self):
        from unittest.mock import patch

        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI",
            return_value=self._openai_returning("désolé, voici du texte libre"),
        ):
            response = self.client.post(
                self.generate_url,
                {"text": "peu importe", "project_id": self.alice_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_generate_injects_current_date_in_system_prompt(self):
        """Le prompt système envoyé à OpenAI contient la date du jour (serveur),
        pour que les échéances relatives soient résolues correctement."""
        import json
        from unittest.mock import patch

        from django.utils import timezone

        content = json.dumps({"tasks": []})
        client = self._openai_returning(content)
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=client):
            self.client.post(
                self.generate_url,
                {"text": "une tâche pour demain", "project_id": self.alice_project.pk},
                format="json",
            )
        # Inspecte les messages réellement passés au client OpenAI mocké.
        _, kwargs = client.chat.completions.create.call_args
        system_message = kwargs["messages"][0]
        self.assertEqual(system_message["role"], "system")
        self.assertIn(timezone.localdate().isoformat(), system_message["content"])

    def test_generate_empty_choices_returns_400(self):
        """Réponse OpenAI sans `choices` → 400, jamais un 500 (IndexError)."""
        from unittest.mock import MagicMock, patch

        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[])
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=client):
            response = self.client.post(
                self.generate_url,
                {"text": "peu importe", "project_id": self.alice_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_generate_openai_unavailable_returns_502(self):
        from unittest.mock import patch

        from openai import OpenAIError

        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI",
            return_value=self._openai_raising(OpenAIError("timeout")),
        ):
            response = self.client.post(
                self.generate_url,
                {"text": "peu importe", "project_id": self.alice_project.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)

    def test_generate_empty_text_returns_400(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.generate_url,
            {"text": "   ", "project_id": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_unauthenticated_returns_401(self):
        response = self.client.post(
            self.generate_url,
            {"text": "peu importe", "project_id": self.alice_project.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- confirm ---

    def test_confirm_creates_tasks(self):
        self.client.force_authenticate(self.alice)
        payload = {
            "project_id": self.alice_project.pk,
            "tasks": [
                {
                    "title": "Tâche 1",
                    "description": "",
                    "priority": "haute",
                    "status": "a_faire",
                    "due_date": "2026-08-15",
                },
                {
                    "title": "Tâche 2",
                    "description": "détail",
                    "priority": "moyenne",
                    "status": "en_cours",
                    "due_date": None,
                },
            ],
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(Task.objects.count(), 2)
        # Rattachées au bon projet, quoi qu'ait pu contenir le corps.
        self.assertTrue(
            all(t.project_id == self.alice_project.pk for t in Task.objects.all())
        )

    def test_confirm_ignores_client_supplied_project_on_task(self):
        """Le projet est fixé côté serveur, jamais pris depuis la tâche du corps."""
        self.client.force_authenticate(self.alice)
        payload = {
            "project_id": self.alice_project.pk,
            "tasks": [
                {
                    "title": "Tâche piégée",
                    # Tentative d'injecter le projet d'un autre utilisateur.
                    "project": self.bob_project.pk,
                    "priority": "moyenne",
                    "status": "a_faire",
                    "due_date": None,
                }
            ],
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get()
        self.assertEqual(task.project_id, self.alice_project.pk)

    def test_confirm_project_of_another_user_returns_404(self):
        self.client.force_authenticate(self.alice)
        payload = {
            "project_id": self.bob_project.pk,
            "tasks": [
                {
                    "title": "Tâche",
                    "priority": "moyenne",
                    "status": "a_faire",
                    "due_date": None,
                }
            ],
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Task.objects.count(), 0)

    def test_confirm_invalid_task_is_atomic_and_returns_400(self):
        """Une seule tâche invalide → 400 et aucune création (tout ou rien)."""
        self.client.force_authenticate(self.alice)
        payload = {
            "project_id": self.alice_project.pk,
            "tasks": [
                {
                    "title": "Valide",
                    "priority": "moyenne",
                    "status": "a_faire",
                    "due_date": None,
                },
                {
                    # Titre vide → invalide côté TaskSerializer.
                    "title": "",
                    "priority": "moyenne",
                    "status": "a_faire",
                    "due_date": None,
                },
            ],
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Task.objects.count(), 0)

    def test_confirm_unauthenticated_returns_401(self):
        payload = {
            "project_id": self.alice_project.pk,
            "tasks": [{"title": "T", "priority": "moyenne", "status": "a_faire"}],
        }
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ChatAPITestCase(APITestCase):
    """Tests de l'assistant conversationnel (cf. tasks/SPEC-ai-chat.md §8).

    L'appel OpenAI est TOUJOURS mocké au niveau du client (`tasks.ai.OpenAI`).
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="pass12345"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="pass12345"
        )
        self.alice_project = Project.objects.create(
            owner=self.alice, name="Projet Alice"
        )
        self.bob_project = Project.objects.create(
            owner=self.bob, name="Projet Bob"
        )
        self.chat_url = reverse("chat")

    def _openai_returning(self, content):
        from unittest.mock import MagicMock

        message = MagicMock()
        message.content = content
        choice = MagicMock()
        choice.message = message
        client = MagicMock()
        client.chat.completions.create.return_value = MagicMock(choices=[choice])
        return client

    def _openai_raising(self, exc):
        from unittest.mock import MagicMock

        client = MagicMock()
        client.chat.completions.create.side_effect = exc
        return client

    def _post(self, messages=None, project_id=None):
        payload = {
            "messages": messages
            or [{"role": "user", "content": "Je veux organiser un événement"}],
            "project_id": project_id,
        }
        return self.client.post(self.chat_url, payload, format="json")

    # --- Conversation en cours ---

    def test_chat_in_progress_returns_reply_without_proposal(self):
        import json
        from unittest.mock import patch

        content = json.dumps(
            {"reply": "Quel est le nom du projet ?", "ready_to_confirm": False,
             "proposal": None}
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["reply"])
        self.assertFalse(response.data["ready_to_confirm"])
        self.assertIsNone(response.data["proposal"])
        # Rien n'est créé par le chat.
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(Project.objects.count(), 2)

    # --- Proposition finale ---

    def test_chat_final_proposal(self):
        import json
        from unittest.mock import patch

        content = json.dumps(
            {
                "reply": "Voici le plan proposé.",
                "ready_to_confirm": True,
                "proposal": {
                    "project": {"name": "Lancement produit", "description": "obj"},
                    "tasks": [
                        {"title": "Rédiger le communiqué", "description": "",
                         "priority": "haute", "status": "a_faire",
                         "due_date": "2026-09-15"},
                    ],
                },
            }
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ready_to_confirm"])
        proposal = response.data["proposal"]
        self.assertEqual(proposal["project"]["name"], "Lancement produit")
        self.assertEqual(len(proposal["tasks"]), 1)
        self.assertEqual(proposal["tasks"][0]["title"], "Rédiger le communiqué")

    def test_chat_proposal_normalizes_out_of_choices_values(self):
        import json
        from unittest.mock import patch

        content = json.dumps(
            {
                "reply": "Plan.",
                "ready_to_confirm": True,
                "proposal": {
                    "project": {"name": "P", "description": ""},
                    "tasks": [
                        {"title": "T", "priority": "urgente", "status": "bloque",
                         "due_date": ""},
                    ],
                },
            }
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post()
        task = response.data["proposal"]["tasks"][0]
        self.assertEqual(task["priority"], Task.Priority.MEDIUM)
        self.assertEqual(task["status"], Task.Status.TODO)
        self.assertIsNone(task["due_date"])

    def test_chat_ready_but_empty_proposal_falls_back_to_not_ready(self):
        """Une proposition annoncée mais vide ne doit pas être marquée prête."""
        import json
        from unittest.mock import patch

        content = json.dumps(
            {"reply": "Plan.", "ready_to_confirm": True,
             "proposal": {"project": {"name": ""}, "tasks": []}}
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ready_to_confirm"])
        self.assertIsNone(response.data["proposal"])

    # --- Contexte projet existant ---

    def test_chat_injects_existing_tasks_for_own_project(self):
        import json
        from unittest.mock import patch

        Task.objects.create(
            title="Tâche existante A", project=self.alice_project
        )
        content = json.dumps(
            {"reply": "ok", "ready_to_confirm": False, "proposal": None}
        )
        client = self._openai_returning(content)
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=client):
            response = self._post(project_id=self.alice_project.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Le prompt système passé à OpenAI contient les tâches existantes.
        _, kwargs = client.chat.completions.create.call_args
        system_content = kwargs["messages"][0]["content"]
        self.assertIn("Tâche existante A", system_content)

    def test_chat_injects_current_date_in_system_prompt(self):
        """La date du jour (serveur) figure dans le prompt système envoyé à
        OpenAI, pour résoudre les dates relatives sans inventer de date passée."""
        import json
        from unittest.mock import patch

        from django.utils import timezone

        content = json.dumps(
            {"reply": "ok", "ready_to_confirm": False, "proposal": None}
        )
        client = self._openai_returning(content)
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=client):
            self._post()
        _, kwargs = client.chat.completions.create.call_args
        system_content = kwargs["messages"][0]["content"]
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        self.assertIn(timezone.localdate().isoformat(), system_content)

    def test_chat_readjust_drops_existing_tasks_from_proposal(self):
        """Réajustement : une tâche proposée au titre déjà existant est retirée,
        seules les nouvelles restent (sinon confirm dupliquerait l'existant)."""
        import json
        from unittest.mock import patch

        Task.objects.create(title="Tâche existante", project=self.alice_project)
        content = json.dumps(
            {
                "reply": "Voici le plan.",
                "ready_to_confirm": True,
                "proposal": {
                    "project": {"name": "Projet Alice", "description": ""},
                    "tasks": [
                        # Doublon (casse/espaces différents) → doit être retiré.
                        {"title": "  tâche EXISTANTE ", "priority": "moyenne",
                         "status": "a_faire", "due_date": None},
                        {"title": "Nouvelle tâche", "priority": "haute",
                         "status": "a_faire", "due_date": None},
                    ],
                },
            }
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post(project_id=self.alice_project.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [t["title"] for t in response.data["proposal"]["tasks"]]
        self.assertEqual(titles, ["Nouvelle tâche"])
        self.assertTrue(response.data["ready_to_confirm"])

    def test_chat_readjust_all_existing_falls_back_to_not_ready(self):
        """Réajustement : si toutes les tâches proposées existent déjà, plus rien
        à ajouter → ready_to_confirm false et proposal null."""
        import json
        from unittest.mock import patch

        Task.objects.create(title="Déjà là", project=self.alice_project)
        content = json.dumps(
            {
                "reply": "Voici le plan.",
                "ready_to_confirm": True,
                "proposal": {
                    "project": {"name": "Projet Alice", "description": ""},
                    "tasks": [
                        {"title": "Déjà là", "priority": "moyenne",
                         "status": "a_faire", "due_date": None},
                    ],
                },
            }
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post(project_id=self.alice_project.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ready_to_confirm"])
        self.assertIsNone(response.data["proposal"])

    def test_chat_new_project_does_not_filter_proposal(self):
        """Sans project_id (nouveau projet), aucune tâche n'est filtrée."""
        import json
        from unittest.mock import patch

        # Une tâche de même titre existe, mais dans un AUTRE projet : hors contexte.
        Task.objects.create(title="Nouvelle tâche", project=self.alice_project)
        content = json.dumps(
            {
                "reply": "Plan.",
                "ready_to_confirm": True,
                "proposal": {
                    "project": {"name": "Tout autre projet", "description": ""},
                    "tasks": [
                        {"title": "Nouvelle tâche", "priority": "moyenne",
                         "status": "a_faire", "due_date": None},
                    ],
                },
            }
        )
        self.client.force_authenticate(self.alice)
        with patch("tasks.ai.OpenAI", return_value=self._openai_returning(content)):
            response = self._post(project_id=None)
        self.assertEqual(len(response.data["proposal"]["tasks"]), 1)

    def test_chat_project_of_another_user_returns_404(self):
        from unittest.mock import patch

        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI", return_value=self._openai_returning("{}")
        ) as mocked:
            response = self._post(project_id=self.bob_project.pk)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mocked.assert_not_called()

    # --- Erreurs ---

    def test_chat_openai_unavailable_returns_502(self):
        from unittest.mock import patch

        from openai import OpenAIError

        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI", return_value=self._openai_raising(OpenAIError("down"))
        ):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)

    def test_chat_unparseable_response_returns_502(self):
        """Décision D2 : réponse non parseable → 502 (pas 400)."""
        from unittest.mock import patch

        self.client.force_authenticate(self.alice)
        with patch(
            "tasks.ai.OpenAI",
            return_value=self._openai_returning("désolé, du texte libre"),
        ):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)

    def test_chat_unauthenticated_returns_401(self):
        response = self._post()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_empty_messages_returns_400(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.chat_url, {"messages": [], "project_id": None}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_chat_malformed_message_returns_400(self):
        self.client.force_authenticate(self.alice)
        response = self.client.post(
            self.chat_url,
            {"messages": [{"role": "user"}], "project_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Flux « nouveau projet » : création en session (D1) ---

    def test_project_create_accepts_session_auth(self):
        """Garantit le flux « nouveau projet » : POST /api/projects/ en session."""
        logged_in = self.client.login(username="alice", password="pass12345")
        self.assertTrue(logged_in)
        response = self.client.post(
            reverse("project-list"),
            {"name": "Projet via assistant", "description": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Project.objects.filter(
                owner=self.alice, name="Projet via assistant"
            ).exists()
        )
