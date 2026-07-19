from django.conf import settings
from django.db import models


class ProjectQuerySet(models.QuerySet):
    """QuerySet de Project, porteur de la règle d'appartenance.

    `for_user()` est la source de vérité unique du « qui voit quoi » côté
    projets : elle est utilisée par les ViewSets DRF, les serializers et les
    futures vues Django classiques, pour qu'aucune de ces couches ne
    réimplémente la règle de son côté.
    """

    def for_user(self, user):
        """Projets dont `user` est propriétaire."""
        return self.filter(owner=user)


class Project(models.Model):
    """Projet appartenant à un utilisateur, conteneur de tâches (V1 solo)."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        # Unicité du nom par propriétaire (pas globale) : deux utilisateurs
        # différents peuvent avoir un projet de même nom.
        unique_together = [["owner", "name"]]

    def __str__(self):
        return self.name
