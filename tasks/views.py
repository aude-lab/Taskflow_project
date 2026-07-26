from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard import build_dashboard
from .filters import TaskFilter
from .models import Task
from .serializers import TaskSerializer


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

    La logique (catégories, fenêtres, exclusion des terminées, « aujourd'hui »
    serveur) vit dans `tasks.dashboard.build_dashboard`, partagée avec le front
    (cf. tasks/SPEC-dashboard.md, core/SPEC-front-dashboard.md). Cette vue ne
    fait que sérialiser le résultat.
    """

    permission_classes = [IsAuthenticated]

    def _serialize(self, queryset):
        tasks = TaskSerializer(
            queryset, many=True, context={"request": self.request}
        ).data
        return {"count": len(tasks), "tasks": tasks}

    def get(self, request):
        data = build_dashboard(request.user)
        return Response(
            {
                "overdue": self._serialize(data["overdue"]),
                "upcoming": self._serialize(data["upcoming"]),
                "by_status": data["by_status"],
            }
        )
