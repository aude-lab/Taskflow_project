"""Helpers d'affichage pour les tâches : badges de couleur et retard.

Présentation uniquement — aucune logique métier. `is_overdue` réutilise la même
définition du « retard » que le tableau de bord (due_date < aujourd'hui serveur
et statut non terminé), côté affichage.
"""

from django import template
from django.utils import timezone

from ..models import Task

register = template.Library()

# Classes de pastille Tailwind (paires fond/texte du design system Material 3).
_DEFAULT_BADGE = "bg-surface-container-high text-on-surface-variant"
STATUS_BADGE = {
    Task.Status.TODO: "bg-surface-container-high text-on-surface-variant",
    Task.Status.IN_PROGRESS: "bg-secondary-fixed text-on-secondary-fixed",
    Task.Status.DONE: "bg-tertiary-container text-on-tertiary-container",
}
PRIORITY_BADGE = {
    Task.Priority.LOW: "bg-surface-variant text-on-surface-variant",
    Task.Priority.MEDIUM: "bg-tertiary-fixed text-on-tertiary-fixed",
    Task.Priority.HIGH: "bg-error-container text-on-error-container",
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
    return {"label": _label(Task.Status, value), "css": STATUS_BADGE.get(value, _DEFAULT_BADGE)}


@register.inclusion_tag("tasks/_badge.html")
def priority_badge(value):
    """Pastille colorée de la priorité ; libellé tiré du modèle."""
    return {
        "label": _label(Task.Priority, value),
        "css": PRIORITY_BADGE.get(value, _DEFAULT_BADGE),
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
