from django.db import IntegrityError, transaction
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    """Inscription : crée le compte et renvoie directement ses tokens JWT.

    Action unique (create), donc pas de ViewSet ni de router : un CreateAPIView
    suffit. Seul endpoint métier ouvert sans authentification.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            # Le serializer a vérifié l'unicité par un SELECT, mais une
            # inscription concurrente peut insérer le même email entre ce SELECT
            # et notre INSERT : la base, elle, refusera. Le savepoint permet de
            # rattraper l'erreur sans laisser la transaction courante inutilisable.
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            raise ValidationError(self._uniqueness_errors(serializer.validated_data))

        # Mêmes tokens que ceux délivrés par /api/token/.
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": serializer.data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _uniqueness_errors(data):
        """Attribue l'IntegrityError au(x) champ(s) réellement en conflit.

        create_user() normalise les deux champs avant l'INSERT (username en
        NFKC, domaine de l'email en minuscules). La relecture porte donc sur les
        valeurs normalisées, c'est-à-dire celles réellement écrites : relire les
        valeurs brutes reviendrait à chercher ce que la base ne contient pas, et
        le conflit serait manqué.

        Renvoie des erreurs de la même forme que celles du serializer. Si aucun
        conflit d'unicité n'explique l'erreur, on laisse remonter : une
        IntegrityError sans rapport doit rester une 500 visible, pas être
        maquillée en 400 trompeuse.
        """
        errors = {}
        username = User.normalize_username(data["username"])
        if User.objects.filter(username=username).exists():
            errors["username"] = ["Ce nom d'utilisateur est déjà pris."]
        email = User.objects.normalize_email(data["email"])
        if User.objects.filter(email=email).exists():
            errors["email"] = ["Cet email est déjà utilisé."]
        if not errors:
            raise
        return errors
