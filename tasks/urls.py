from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChatView,
    ConfirmTasksView,
    DashboardView,
    GenerateTasksView,
    TaskViewSet,
)

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")

# Les routes de l'assistant IA sont déclarées AVANT celles du router : `generate`
# et `confirm` ne sont pas des pk, il n'y a pas de collision avec `tasks/<pk>/`,
# mais on garde ces chemins explicites en tête pour la lisibilité.
urlpatterns = [
    path("tasks/generate/", GenerateTasksView.as_view(), name="task_generate"),
    path("tasks/confirm/", ConfirmTasksView.as_view(), name="task_confirm"),
    path("chat/", ChatView.as_view(), name="chat"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
] + router.urls
