from core.forms import BootstrapFormMixin
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    """Formulaire de connexion — AuthenticationForm de Django, stylé Bootstrap."""


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Inscription depuis le front.

    UserCreationForm fournit déjà la confirmation du mot de passe (password1 /
    password2) et applique AUTH_PASSWORD_VALIDATORS en lui passant l'instance,
    ce qui rend effectif UserAttributeSimilarityValidator. Le hachage est fait
    par son `save()` : jamais de mot de passe en clair en base.

    `email` est obligatoire et unique par le modèle (cf. accounts/SPEC.md) :
    l'unicité remonte donc en erreur de formulaire, pas en 500.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]
