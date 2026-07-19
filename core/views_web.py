from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class HomeView(LoginRequiredMixin, TemplateView):
    """Accueil du front — placeholder du futur tableau de bord.

    `LoginRequiredMixin` n'est pas cosmétique : les vues front manipulant des
    données passent par les managers `for_user()`, qui supposent un utilisateur
    authentifié. Sans le mixin, un visiteur anonyme provoquerait une 500 au lieu
    d'être redirigé vers la connexion.
    """

    template_name = "core/home.html"
