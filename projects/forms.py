from core.forms import BootstrapFormMixin
from django import forms

from .models import Project


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    """Création et modification d'un projet depuis le front.

    `owner` n'est volontairement pas un champ du formulaire : il est fixé côté
    serveur par la vue. Mais comme Django exclut de `validate_unique()` les
    champs absents du formulaire, la contrainte `unique_together (owner, name)`
    du modèle serait **ignorée à la validation** — le doublon n'échouerait qu'à
    l'INSERT, en IntegrityError, donc en 500.

    D'où la vérification explicite dans `clean_name()`, qui reprend exactement
    la règle de `ProjectSerializer.validate_name` et passe par le même manager.
    """

    class Meta:
        model = Project
        fields = ["name", "description"]
        labels = {"name": "Nom", "description": "Description"}

    def __init__(self, *args, user, **kwargs):
        # `user` est obligatoire : avec une valeur par défaut à None,
        # for_user(None) filtrerait sur `owner IS NULL`, ne matcherait jamais,
        # et désactiverait silencieusement la vérification d'unicité ci-dessous.
        # Mieux vaut échouer bruyamment si un appelant l'oublie.
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        value = self.cleaned_data["name"]
        queryset = Project.objects.for_user(self.user).filter(name=value)
        # En modification, exclure l'instance courante pour autoriser un
        # enregistrement qui conserve son propre nom.
        if self.instance.pk is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Vous avez déjà un projet portant ce nom.")
        return value
