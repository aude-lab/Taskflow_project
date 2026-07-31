from django.urls import path

from .views_web import AssistantView, HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("assistant/", AssistantView.as_view(), name="assistant"),
]
