from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from projects.models import Project
from tasks.dashboard import build_dashboard
from tasks.models import Task


class HomeView(LoginRequiredMixin, TemplateView):
    """Accueil du front = tableau de bord (en retard / à venir / par statut).

    La logique du dashboard est partagée avec l'API via `build_dashboard`
    (tasks.dashboard), pour que les deux ne divergent pas.

    `LoginRequiredMixin` n'est pas cosmétique : `build_dashboard` passe par
    `for_user()`, qui suppose un utilisateur authentifié. Comme il n'est appelé
    que dans `get_context_data` (après `dispatch`), un visiteur anonyme est
    redirigé vers la connexion avant tout accès aux données.
    """

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = build_dashboard(self.request.user)
        context.update(dashboard)
        # Compteurs par statut avec les libellés accentués du modèle, dans
        # l'ordre déclaré de Status (a_faire, en_cours, termine).
        context["by_status_display"] = [
            (status.label, dashboard["by_status"][status.value])
            for status in Task.Status
        ]
        return context


class AssistantView(LoginRequiredMixin, TemplateView):
    """Page de chat de l'assistant IA de planification (cf. SPEC-ai-chat.md §5.1).

    Sert la coquille HTML ; toute la conversation vit côté JS et dialogue avec
    `POST /api/chat/`. Un `?project_id=<pk>` (mode « réajuster ») n'est transmis
    au template que s'il désigne un projet de l'utilisateur — sinon on retombe
    silencieusement sur le mode « nouveau projet », sans révéler l'existence d'un
    projet d'autrui.
    """

    template_name = "core/assistant.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = None
        raw_id = self.request.GET.get("project_id")
        if raw_id and raw_id.isdigit():
            context["project"] = (
                Project.objects.for_user(self.request.user)
                .filter(pk=int(raw_id))
                .first()
            )
        return context
