"""Requêtes partagées définissant « qui voit quoi » (cf. core/SPEC-queries.md).

Source de vérité unique du filtrage par utilisateur, utilisée aussi bien par les
ViewSets DRF que par les futures vues Django classiques : deux implémentations
séparées de cette règle finiraient par diverger, et une divergence ici est une
faille d'isolation.

Ces fonctions prennent un `user` (et non une `request`) pour rester utilisables
depuis les deux mondes. Elles supposent un utilisateur authentifié : c'est à
l'appelant de le garantir (`IsAuthenticated` côté DRF).
"""

from projects.models import Project
from tasks.models import Task


def get_user_projects(user):
    """Projets dont `user` est propriétaire."""
    return Project.objects.filter(owner=user)


def get_user_tasks(user):
    """Tâches rattachées aux projets de `user`.

    L'appartenance est indirecte : elle passe par le projet parent. Le
    `select_related` évite de refaire une requête sur `project` côté appelant.
    """
    return Task.objects.filter(project__owner=user).select_related("project")
