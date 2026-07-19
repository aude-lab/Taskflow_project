from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import RegistrationForm


class RegistrationView(CreateView):
    """Création de compte depuis le front, suivie d'une connexion automatique."""

    form_class = RegistrationForm
    template_name = "accounts/registration.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        # LoginView a l'option redirect_authenticated_user ; CreateView non.
        # Sans cette redirection, un utilisateur connecté verrait le formulaire.
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Votre compte a bien été créé.")
        return response
