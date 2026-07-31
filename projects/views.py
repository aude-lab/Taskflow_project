from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD des projets de l'utilisateur connecté.

    Chaque utilisateur ne voit et ne modifie que ses propres projets : le
    queryset est filtré par `owner`, si bien qu'un projet d'un autre utilisateur
    renvoie 404 (et non 403) — on ne révèle pas son existence.

    Accepte la `SessionAuthentication` en plus du JWT (ajout additif, cf.
    SPEC-ai-chat.md D1) : l'assistant conversationnel crée un nouveau projet
    depuis le front rendu en session (`POST /api/projects/` en `fetch`) avant
    d'y rattacher les tâches. JWT reste en tête pour un 401 (et non 403) sur
    accès anonyme ; la session impose alors le CSRF.
    """

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
