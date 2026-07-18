from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin de User.

    Sous-classe UserAdmin (et non ModelAdmin) pour conserver le formulaire de
    mot de passe hashé ; on ne surcharge que l'affichage en liste et la
    recherche.
    """

    list_display = ("username", "email", "is_staff")
    search_fields = ("username", "email")
