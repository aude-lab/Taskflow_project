from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
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
