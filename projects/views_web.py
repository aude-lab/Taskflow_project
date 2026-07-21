from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ProjectForm
from .models import Project

PROJECT_LIST_URL = reverse_lazy("project_list")


class UserProjectMixin(LoginRequiredMixin):
    """Base des vues projet du front.

    `get_queryset()` filtre toujours par utilisateur : un projet d'autrui est
    hors du queryset, donc renvoie 404 (et non 403) — on ne révèle pas son
    existence, comme côté API.

    `LoginRequiredMixin` est indispensable : `for_user()` suppose un utilisateur
    authentifié, un anonyme provoquerait une 500 au lieu d'une redirection.
    """

    model = Project

    def get_queryset(self):
        return Project.objects.for_user(self.request.user)


class ProjectFormMixin:
    """Passe l'utilisateur au formulaire et fixe l'owner côté serveur."""

    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = PROJECT_LIST_URL

    def get_form_kwargs(self):
        # Le formulaire en a besoin pour vérifier l'unicité (owner, name).
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ProjectListView(UserProjectMixin, ListView):
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        # Agrégation : le nombre de tâches ne doit pas coûter une requête par
        # projet.
        return super().get_queryset().annotate(task_count=Count("tasks"))


class ProjectDetailView(UserProjectMixin, DetailView):
    template_name = "projects/project_detail.html"
    context_object_name = "project"


class ProjectCreateView(UserProjectMixin, ProjectFormMixin, CreateView):
    def form_valid(self, form):
        # L'owner est fixé côté serveur, jamais accepté du client.
        form.instance.owner = self.request.user
        # Message émis après la sauvegarde : annoncer le succès avant qu'elle
        # ait eu lieu afficherait « Projet créé » même si l'écriture échouait.
        response = super().form_valid(form)
        messages.success(self.request, "Projet créé.")
        return response


class ProjectUpdateView(UserProjectMixin, ProjectFormMixin, UpdateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Projet modifié.")
        return response


class ProjectDeleteView(UserProjectMixin, DeleteView):
    template_name = "projects/project_confirm_delete.html"
    context_object_name = "project"
    success_url = PROJECT_LIST_URL

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Rendre visible la conséquence du CASCADE avant de confirmer.
        context["task_count"] = self.object.tasks.count()
        return context

    def form_valid(self, form):
        # SuccessMessageMixin ne convient pas ici : l'objet est supprimé avant
        # que le message ne puisse être composé à partir de lui.
        response = super().form_valid(form)
        messages.success(self.request, "Projet supprimé.")
        return response
