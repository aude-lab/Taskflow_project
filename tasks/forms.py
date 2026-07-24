from core.forms import BootstrapFormMixin
from django import forms

from .models import Task


class TaskForm(BootstrapFormMixin, forms.ModelForm):
    """Création et modification d'une tâche depuis le front.

    `project` n'est pas un champ : il vient de l'URL en création (fixé par la
    vue) et ne change pas en modification. Task n'a aucune contrainte d'unicité,
    donc pas de `clean_*` ni de `user` à passer — contrairement à ProjectForm.
    """

    # Déclaré explicitement pour porter trois réglages indissociables :
    # - required=False : le déclarer fait perdre l'héritage `blank=True` du modèle ;
    # - input_formats : le format soumis par <input type="date"> (AAAA-MM-JJ) ;
    # - widget format : sans lui, une date existante se ré-afficherait en
    #   JJ/MM/AAAA (locale fr) → invalide pour <input type="date">, qui s'ouvrirait
    #   VIDE sur une tâche datée.
    due_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        label="Échéance",
    )

    class Meta:
        model = Task
        fields = ["title", "description", "status", "priority", "due_date"]
        labels = {
            "title": "Titre",
            "description": "Description",
            "status": "Statut",
            "priority": "Priorité",
        }
