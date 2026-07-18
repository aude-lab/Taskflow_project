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
        fields["project"].queryset = Project.objects.filter(
            owner=self.context["request"].user
        )
        return fields
