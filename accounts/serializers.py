from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Inscription d'une nouvelle utilisatrice.

    L'unicité de `username` et d'`email` est portée par la base et remontée
    automatiquement par le ModelSerializer : aucune validation custom ici.

    `password` et `password_confirm` sont `write_only`, donc `serializer.data`
    ne renvoie que `id`, `username` et `email` — inutile d'ajouter un serializer
    de sortie dédié.
    """

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "password_confirm"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Les deux mots de passe ne correspondent pas."}
            )

        # validate_password a besoin d'une instance User pour que
        # UserAttributeSimilarityValidator puisse comparer le mot de passe au
        # username et à l'email. L'utilisatrice n'existe pas encore : on lui
        # passe une instance non sauvegardée.
        user = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            # validate_password lève une ValidationError *Django* ; sans cette
            # conversion vers celle de DRF, on renverrait une 500 au lieu d'un 400.
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        # create_user() hashe le mot de passe (set_password). Ne JAMAIS utiliser
        # User.objects.create(), qui le stockerait en clair en base.
        return User.objects.create_user(**validated_data)
