"""
URL configuration for taskflow project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # Inscription (seul endpoint métier ouvert sans authentification)
    path('api/', include('accounts.urls')),
    # Authentification JWT (djangorestframework-simplejwt)
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Ressources métier
    path('api/', include('projects.urls')),
    path('api/', include('tasks.urls')),
    # Front (vues Django classiques, authentification par session)
    path('', include('accounts.urls_web')),
    path('', include('core.urls_web')),
]
