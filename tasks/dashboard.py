"""Logique du tableau de bord, partagée par l'API et le front.

Source unique des définitions « en retard / à venir / par statut », pour que
`DashboardView` (API) et `HomeView` (front) ne divergent pas. Prend un `user`
(pas une `request`), cohérent avec `Task.objects.for_user`.
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .filters import TaskFilter
from .models import Task

UPCOMING_WINDOW_DAYS = 14


def build_dashboard(user):
    """Catégories du tableau de bord pour `user`.

    Renvoie des QuerySet **non évalués** pour `overdue`/`upcoming` (l'appelant
    les sérialise ou les rend directement) et un dict pour `by_status`. Toutes
    les catégories dérivent de `Task.objects.for_user(user)` — jamais
    `Task.objects.all()` — et `aujourd'hui` est calculé côté serveur, sans
    aucune entrée du client.
    """
    base = Task.objects.for_user(user)
    today = timezone.localdate()
    horizon = today + timedelta(days=UPCOMING_WINDOW_DAYS)

    # Réutilise TaskFilter (tasks/filters.py) pour les bornes de date plutôt que
    # de les réécrire. Le filtre s'applique sur `base` déjà restreint à
    # l'utilisateur : il ne peut que réduire. `.exclude(DONE)` retire les tâches
    # terminées, qui ne sont ni « en retard » ni « à venir ».
    # < aujourd'hui : la borne du filtre étant `lte`, on vise la veille.
    overdue = TaskFilter(
        {"due_date_before": today - timedelta(days=1)}, queryset=base
    ).qs.exclude(status=Task.Status.DONE)
    # [aujourd'hui, aujourd'hui + 14 jours], bornes incluses.
    upcoming = TaskFilter(
        {"due_date_after": today, "due_date_before": horizon}, queryset=base
    ).qs.exclude(status=Task.Status.DONE)

    by_status = {status: 0 for status in Task.Status.values}
    for row in base.values("status").annotate(count=Count("id")):
        by_status[row["status"]] = row["count"]

    return {"overdue": overdue, "upcoming": upcoming, "by_status": by_status}
