from django.conf import settings
from django.db import models


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

    class Meta:
        ordering = ["-created_at"]
        # Unicité du nom par propriétaire (pas globale) : deux utilisateurs
        # différents peuvent avoir un projet de même nom.
        unique_together = [["owner", "name"]]

    def __str__(self):
        return self.name
