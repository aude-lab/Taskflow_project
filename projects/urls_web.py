from django.urls import path

from .views_web import (
    ProjectCreateView,
    ProjectDeleteView,
    ProjectDetailView,
    ProjectListView,
    ProjectUpdateView,
)

urlpatterns = [
    path("projets/", ProjectListView.as_view(), name="project_list"),
    path("projets/nouveau/", ProjectCreateView.as_view(), name="project_create"),
    path("projets/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),
    path(
        "projets/<int:pk>/modifier/",
        ProjectUpdateView.as_view(),
        name="project_update",
    ),
    path(
        "projets/<int:pk>/supprimer/",
        ProjectDeleteView.as_view(),
        name="project_delete",
    ),
]
