from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import CreateView, DeleteView, UpdateView
from projects.models import Project

from .forms import TaskForm
from .models import Task


class TaskCreateView(LoginRequiredMixin, CreateView):
    """Créer une tâche dans un projet dont le pk est porté par l'URL.

    Le projet parent est chargé via `for_user()` : créer une tâche dans le
    projet d'autrui donne 404, on ne révèle pas son existence. Il n'est jamais
    pris depuis le POST.
    """

    form_class = TaskForm
    template_name = "tasks/task_form.html"

    @cached_property
    def project(self):
        # cached_property (et non setup/dispatch) : n'est consommée que dans les
        # handlers, donc APRÈS LoginRequiredMixin. Un anonyme est redirigé (302)
        # avant tout accès, au lieu d'un for_user(AnonymousUser) → 404.
        return get_object_or_404(
            Project.objects.for_user(self.request.user),
            pk=self.kwargs["project_pk"],
        )

    def form_valid(self, form):
        form.instance.project = self.project
        response = super().form_valid(form)
        messages.success(self.request, "Tâche créée.")
        return response

    def get_success_url(self):
        return reverse("project_detail", kwargs={"pk": self.project.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        return context


class UserTaskMixin(LoginRequiredMixin):
    """Base des vues qui opèrent sur une tâche existante (modif / suppression).

    `get_queryset()` filtre par utilisateur : une tâche d'autrui est hors du
    queryset → 404 (et non 403). `for_user()` porte déjà `select_related(
    'project')`, donc accéder au projet parent (redirection, message) ne coûte
    pas de requête supplémentaire.
    """

    model = Task

    def get_queryset(self):
        return Task.objects.for_user(self.request.user)

    def get_success_url(self):
        return reverse("project_detail", kwargs={"pk": self.object.project.pk})


class TaskUpdateView(UserTaskMixin, UpdateView):
    form_class = TaskForm
    template_name = "tasks/task_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.object.project
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Tâche modifiée.")
        return response


class TaskDeleteView(UserTaskMixin, DeleteView):
    template_name = "tasks/task_confirm_delete.html"
    context_object_name = "task"

    def form_valid(self, form):
        # get_success_url() est appelée par DeletionMixin AVANT la suppression,
        # donc self.object.project est encore accessible (sans requête grâce au
        # select_related). Le message référence l'objet Python en mémoire.
        response = super().form_valid(form)
        messages.success(self.request, "Tâche supprimée.")
        return response
