from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLES = [
        ('DIRECTEUR', 'Directeur'),
        ('CENSEUR', 'Censeur'),
        ('PROFESSEUR', 'Professeur'),
        ('COMPTABLE', 'Comptable'),
        ('SURVEILLANT', 'Surveillant'),
        ('SECRETAIRE', 'Secrétaire'),
        ('PARENT', 'Parent'),
        ('ELEVE', 'Élève'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='ELEVE')
    telephone = models.CharField(max_length=20, blank=True)
    telephone_wa = models.CharField(max_length=20, blank=True,
        help_text="Numéro WhatsApp avec indicatif ex: +22890000000")
    wa_verifie = models.BooleanField(default=False)
    photo = models.ImageField(upload_to='photos/personnel/', null=True, blank=True)
    adresse = models.CharField(max_length=200, blank=True)
    specialite = models.CharField(max_length=100, blank=True)
    date_prise_service = models.DateField(null=True, blank=True)
    preferences_notifications = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def nom_complet(self):
        return self.get_full_name() or self.username

    def has_role(self, *roles):
        return self.role in roles