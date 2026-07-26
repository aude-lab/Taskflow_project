from django.urls import path

from .views_web import (
    TaskCreateView,
    TaskDeleteView,
    TaskListView,
    TaskUpdateView,
)

urlpatterns = [
    path("taches/", TaskListView.as_view(), name="task_list"),
    path(
        "projets/<int:project_pk>/taches/nouvelle/",
        TaskCreateView.as_view(),
        name="task_create",
    ),
    path("taches/<int:pk>/modifier/", TaskUpdateView.as_view(), name="task_update"),
    path("taches/<int:pk>/supprimer/", TaskDeleteView.as_view(), name="task_delete"),
]
