from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'nom_complet', 'role', 'telephone_wa', 'wa_verifie', 'is_active']
    list_filter = ['role', 'is_active', 'wa_verifie']
    fieldsets = UserAdmin.fieldsets + (
        ('GESTo', {'fields': (
            'role', 'telephone', 'telephone_wa', 'wa_verifie',
            'photo', 'adresse', 'specialite', 'preferences_notifications'
        )}),
    )
