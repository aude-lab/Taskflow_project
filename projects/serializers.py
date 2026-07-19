from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer de Project.

    `owner` n'est pas exposé : il est fixé côté serveur (perform_create) à
    l'utilisateur courant. On ne peut donc pas s'appuyer sur le
    UniqueTogetherValidator automatique de DRF (qui exigerait `owner` dans les
    champs) ; l'unicité (owner, name) est vérifiée manuellement ci-dessous.
    """

    class Meta:
        model = Project
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        user = self.context["request"].user
        queryset = Project.objects.for_user(user).filter(name=value)
        # En update, exclure l'instance courante pour autoriser un enregistrement
        # qui conserve son propre nom.
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Vous avez déjà un projet portant ce nom."
            )
        return value
