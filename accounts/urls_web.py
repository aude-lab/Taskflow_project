from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .forms import LoginForm
from .views_web import RegistrationView

urlpatterns = [
    path(
        "connexion/",
        LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    # LogoutView n'accepte que POST depuis Django 5 (un GET renvoie 405).
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("inscription/", RegistrationView.as_view(), name="registration"),
]
