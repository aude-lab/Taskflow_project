from projects.models import Project
from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    """Serializer de Task.

    Contrairement à `Project.owner`, le champ `project` est fourni par le client.
    Sa sécurité repose sur un queryset restreint aux projets de l'utilisateur
    courant (cf. `get_fields`), et non sur une validation custom : un projet
    d'autrui est alors rejeté par DRF lui-même, exactement comme un projet
    inexistant. La fuite d'information est impossible par construction.
    """

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "project",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        fields["project"].queryset = Project.objects.for_user(
            self.context["request"].user
        )
        return fields


class GenerateTasksSerializer(serializers.Serializer):
    """Valide l'entrée de POST /api/tasks/generate/ (assistant IA).

    Ne mappe aucun modèle : on vérifie seulement que le texte à analyser et le
    projet cible sont fournis. L'appartenance du projet est revérifiée dans la
    vue via `for_user()` (404), jamais ici.
    """

    text = serializers.CharField(trim_whitespace=True)
    project_id = serializers.IntegerField()


class ConfirmTasksSerializer(serializers.Serializer):
    """Valide l'entrée de POST /api/tasks/confirm/ (assistant IA).

    Le `project_id` est revérifié via `for_user()` dans la vue (404). Chaque
    tâche est ensuite revalidée par `TaskSerializer` à la création : on ne fait
    jamais confiance aux données du client, même issues de l'aperçu IA.
    """

    project_id = serializers.IntegerField()
    tasks = serializers.ListField(
        child=serializers.DictField(), allow_empty=False
    )


class ChatMessageSerializer(serializers.Serializer):
    """Un message de l'historique de conversation renvoyé par le front."""

    role = serializers.ChoiceField(choices=["user", "assistant"])
    # allow_blank : un message assistant au contenu vide (reply vide renvoyé par
    # le modèle) ne doit pas faire échouer l'appel suivant qui renvoie tout
    # l'historique.
    content = serializers.CharField(allow_blank=True)


class ChatSerializer(serializers.Serializer):
    """Valide l'entrée de POST /api/chat/ (assistant conversationnel).

    `messages` est l'historique complet renvoyé par le front à chaque appel (pas
    de mémoire serveur). `project_id` est optionnel : `null`/absent pour un
    nouveau projet, sinon l'id d'un projet dont l'appartenance est revérifiée
    dans la vue via `for_user()` (404).
    """

    messages = ChatMessageSerializer(many=True, allow_empty=False)
    project_id = serializers.IntegerField(
        required=False, allow_null=True, default=None
    )
