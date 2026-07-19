from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD des projets de l'utilisateur connecté.

    Chaque utilisateur ne voit et ne modifie que ses propres projets : le
    queryset est filtré par `owner`, si bien qu'un projet d'un autre utilisateur
    renvoie 404 (et non 403) — on ne révèle pas son existence.
    """

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
