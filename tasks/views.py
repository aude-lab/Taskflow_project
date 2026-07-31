from django.db import transaction
from django.shortcuts import get_object_or_404
from projects.models import Project
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .ai import AIServiceError, generate_tasks
from .dashboard import build_dashboard
from .filters import TaskFilter
from .models import Task
from .serializers import (
    ConfirmTasksSerializer,
    GenerateTasksSerializer,
    TaskSerializer,
)


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


class AIAssistantView(APIView):
    """Base des deux endpoints de l'assistant IA (génération de tâches).

    Contrairement au reste de l'API (JWT uniquement), ces vues sont appelées en
    `fetch` par le front rendu en session : elles acceptent donc aussi la
    `SessionAuthentication` (qui impose le CSRF), sans toucher au réglage global
    (cf. SPEC-ai-assistant.md §3). Un anonyme reçoit 401.
    """

    # JWT en tête (et non Session) : DRF dérive le choix 401 vs 403 de l'en-tête
    # d'authentification du PREMIER authenticator. `SessionAuthentication` n'en
    # fournit pas → un anonyme recevrait 403 ; `JWTAuthentication` fournit
    # « Bearer », ce qui donne bien 401 (§8, cas non authentifié). L'ordre
    # n'affecte pas la réussite de l'authentification : les deux restent tentés,
    # et la Session impose toujours le CSRF quand c'est elle qui authentifie.
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_project(self, project_id):
        """Charge le projet cible en le restreignant à l'utilisateur courant.

        Un projet inexistant ou appartenant à autrui donne 404 : on ne révèle
        pas son existence, comme partout dans le projet. Vaut aussi bien pour
        `generate` que pour `confirm` : on ne fait jamais confiance au
        `project_id` fourni par le client sans le revérifier.
        """
        return get_object_or_404(
            Project.objects.for_user(self.request.user), pk=project_id
        )


class GenerateTasksView(AIAssistantView):
    """POST /api/tasks/generate/ — propose des tâches à partir d'un texte libre.

    N'écrit RIEN en base : renvoie un aperçu que l'utilisateur validera avant
    création (via `ConfirmTasksView`).
    """

    def post(self, request):
        serializer = GenerateTasksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 404 si le projet n'est pas à l'utilisateur, avant tout appel externe.
        self.get_project(serializer.validated_data["project_id"])

        try:
            tasks = generate_tasks(serializer.validated_data["text"])
        except AIServiceError as exc:
            # Réponse inexploitable du modèle → 400 ; indisponibilité → 502.
            # Jamais de 500 silencieux.
            code = (
                status.HTTP_400_BAD_REQUEST
                if exc.unparseable
                else status.HTTP_502_BAD_GATEWAY
            )
            return Response({"detail": str(exc)}, status=code)

        return Response({"tasks": tasks})


class ConfirmTasksView(AIAssistantView):
    """POST /api/tasks/confirm/ — crée réellement les tâches validées par l'user.

    Chaque tâche est revalidée par `TaskSerializer` (choices, longueurs, date) :
    les données viennent du client, pas directement de l'IA. Création en
    transaction atomique : une seule tâche invalide → 400 et aucune création.
    """

    def post(self, request):
        serializer = ConfirmTasksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = self.get_project(serializer.validated_data["project_id"])

        # Le projet est fixé côté serveur, jamais pris depuis les tâches du corps.
        payloads = [
            {**{k: v for k, v in task.items() if k != "project"},
             "project": project.pk}
            for task in serializer.validated_data["tasks"]
        ]
        task_serializer = TaskSerializer(
            data=payloads, many=True, context={"request": request}
        )
        task_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            task_serializer.save()

        return Response(task_serializer.data, status=status.HTTP_201_CREATED)
