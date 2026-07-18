from django.db import models


class Task(models.Model):
    """Tâche rattachée à un projet (V1 solo).

    L'appartenance à un utilisateur est indirecte : elle découle du projet
    parent (`project.owner`). Il n'y a donc pas de champ `owner` ici.
    """

    class Status(models.TextChoices):
        TODO = "a_faire", "À faire"
        IN_PROGRESS = "en_cours", "En cours"
        DONE = "termine", "Terminé"

    class Priority(models.TextChoices):
        LOW = "basse", "Basse"
        MEDIUM = "moyenne", "Moyenne"
        HIGH = "haute", "Haute"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    # Une échéance passée est volontairement autorisée : c'est ce qui rend une
    # tâche « en retard » au tableau de bord.
    due_date = models.DateField(null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
