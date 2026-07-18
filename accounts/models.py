from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur de TaskFlow.

    Aucun champ supplémentaire par rapport à AbstractUser : `email` est
    seulement redéfini pour être obligatoire et unique (cf. ci-dessous).

    On définit malgré tout un modèle User custom dès l'initialisation du projet,
    car changer AUTH_USER_MODEL une fois les migrations appliquées est très
    coûteux : de nombreuses tables (auth, admin, et à terme Project/Task) créent
    des clés étrangères vers l'utilisateur dès le premier `migrate`. Poser ce
    modèle maintenant, même vide, garantit la liberté d'ajouter des champs plus
    tard via une simple migration, sans reconstruire la base.

    Note : aucune anticipation de la V2 ici (pas de rôle, d'équipe ni de
    notion de partage).
    """

    # AbstractUser.email est `blank=True` et sans contrainte d'unicité. On le
    # redéfinit pour que l'unicité soit garantie par la base plutôt que par une
    # validation serializer, qui laisserait passer deux inscriptions simultanées
    # avec le même email. `blank=False` (défaut) le rend aussi obligatoire.
    email = models.EmailField(unique=True)
