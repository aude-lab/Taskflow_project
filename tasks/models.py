from django.db import models


class TaskQuerySet(models.QuerySet):
    """QuerySet de Task, porteur de la règle d'appartenance.

    `for_user()` est la source de vérité unique du « qui voit quoi » côté
    tâches : elle est utilisée par les ViewSets DRF, le tableau de bord et les
    futures vues Django classiques.
    """

    def for_user(self, user):
        """Tâches rattachées aux projets de `user`.

        L'appartenance est indirecte : elle passe par le projet parent. Le
        `select_related` évite une requête supplémentaire sur `project`.
        """
        return self.filter(project__owner=user).select_related("project")


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

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
