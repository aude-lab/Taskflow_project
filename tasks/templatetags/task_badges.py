"""Helpers d'affichage pour les tâches : badges de couleur et retard.

Présentation uniquement — aucune logique métier. `is_overdue` réutilise la même
définition du « retard » que le tableau de bord (due_date < aujourd'hui serveur
et statut non terminé), côté affichage.
"""

from django import template
from django.utils import timezone

from ..models import Task

register = template.Library()

STATUS_BADGE = {
    Task.Status.TODO: "secondary",
    Task.Status.IN_PROGRESS: "primary",
    Task.Status.DONE: "success",
}
PRIORITY_BADGE = {
    Task.Priority.LOW: "secondary",
    Task.Priority.MEDIUM: "warning",
    Task.Priority.HIGH: "danger",
}


def _label(enum, value):
    """Libellé accentué du choix, ou la valeur brute si elle est inconnue —
    un helper d'affichage ne doit jamais faire planter la page."""
    try:
        return enum(value).label
    except ValueError:
        return value


@register.inclusion_tag("tasks/_badge.html")
def status_badge(value):
    """Pastille colorée du statut ; libellé tiré du modèle."""
    return {"label": _label(Task.Status, value), "css": STATUS_BADGE.get(value, "secondary")}


@register.inclusion_tag("tasks/_badge.html")
def priority_badge(value):
    """Pastille colorée de la priorité ; libellé tiré du modèle."""
    return {
        "label": _label(Task.Priority, value),
        "css": PRIORITY_BADGE.get(value, "secondary"),
    }


@register.filter
def is_overdue(task):
    """Une tâche est en retard si son échéance est passée et qu'elle n'est pas
    terminée. `aujourd'hui` est calculé côté serveur."""
    return (
        task.due_date is not None
        and task.due_date < timezone.localdate()
        and task.status != Task.Status.DONE
    )
