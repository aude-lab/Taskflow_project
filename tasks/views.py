from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import TaskFilter
from .models import Task
from .serializers import TaskSerializer

UPCOMING_WINDOW_DAYS = 14


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD des tâches des projets de l'utilisateur connecté.

    Le filtrage passe par le projet parent (`project__owner`) : une tâche d'un
    autre utilisateur renvoie 404 (et non 403), on ne révèle pas son existence.
    `select_related('project')` est une précaution contre les N+1 : aujourd'hui
    `project` est sérialisé par son seul pk (déjà présent sur la ligne), mais le
    JOIN est de toute façon fait pour le filtre.
    """

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TaskFilter

    def get_queryset(self):
        return Task.objects.for_user(self.request.user)


class DashboardView(APIView):
    """Vue d'ensemble des tâches de l'utilisateur : en retard, à venir, par statut.

    Toutes les catégories dérivent du queryset restreint à l'utilisateur (jamais
    `Task.objects.all()`), et `aujourd'hui` est calculé côté serveur, sans aucune
    entrée du client (cf. tasks/SPEC-dashboard.md §5).
    """

    permission_classes = [IsAuthenticated]

    def base_queryset(self):
        return Task.objects.for_user(self.request.user)

    def _apply_filter(self, base, params):
        # Réutilise TaskFilter (tasks/filters.py) plutôt que de réécrire les
        # bornes de date. Le filtre s'applique sur `base` déjà restreint à
        # l'utilisateur : il ne peut que réduire, jamais élargir.
        return TaskFilter(params, queryset=base, request=self.request).qs

    def _serialize(self, queryset):
        tasks = TaskSerializer(
            queryset, many=True, context={"request": self.request}
        ).data
        return {"count": len(tasks), "tasks": tasks}

    def get(self, request):
        base = self.base_queryset()
        today = timezone.localdate()
        horizon = today + timedelta(days=UPCOMING_WINDOW_DAYS)

        # < aujourd'hui : la borne du filtre étant `lte`, on vise la veille.
        overdue = self._apply_filter(
            base, {"due_date_before": today - timedelta(days=1)}
        ).exclude(status=Task.Status.DONE)
        # [aujourd'hui, aujourd'hui + 14 jours], bornes incluses.
        upcoming = self._apply_filter(
            base, {"due_date_after": today, "due_date_before": horizon}
        ).exclude(status=Task.Status.DONE)

        by_status = {status: 0 for status in Task.Status.values}
        for row in base.values("status").annotate(count=Count("id")):
            by_status[row["status"]] = row["count"]

        return Response(
            {
                "overdue": self._serialize(overdue),
                "upcoming": self._serialize(upcoming),
                "by_status": by_status,
            }
        )
