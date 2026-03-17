from django.db import models


class ConfigurationEcole(models.Model):
    SYSTEMES = [
        ('TRIMESTRIEL', 'Trimestriel (T1/T2/T3)'),
        ('SEMESTRIEL', 'Semestriel (S1/S2)'),
    ]
    TYPES_ECOLE = [
        ('PRIVE', 'Établissement privé'),
        ('PUBLIC', 'Établissement public'),
    ]
    nom = models.CharField(max_length=200, default='GESTo')
    slogan = models.CharField(max_length=200, blank=True)
    adresse = models.CharField(max_length=300, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='config/', null=True, blank=True)
    type_ecole = models.CharField(
        max_length=10, choices=TYPES_ECOLE, default='PRIVE'
    )
    systeme_defaut = models.CharField(
        max_length=15, choices=SYSTEMES, default='TRIMESTRIEL'
    )
    region = models.CharField(max_length=100, blank=True)
    ministre_tutelle = models.CharField(max_length=200, blank=True)
    devise = models.CharField(
        max_length=100, blank=True,
        default='Travail – Liberté – Patrie'
    )
    heure_rapport_directeur = models.TimeField(default='09:00')
    heure_rapport_censeur = models.TimeField(default='18:00')
    seuil_retards_consecutifs = models.IntegerField(default=5)
    seuil_retards_periode = models.IntegerField(default=10)
    seuil_jours_periode = models.IntegerField(default=20)
    seuil_alerte_dette_jours = models.IntegerField(default=30)
    wa_numero_source = models.CharField(max_length=20, blank=True)
    wa_numero_secours = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration école'

    def __str__(self):
        return self.nom

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SauvegardeAuto(models.Model):
    TYPES = [
        ('AUTOMATIQUE', 'Automatique'),
        ('MANUELLE', 'Manuelle'),
    ]
    STATUTS = [
        ('SUCCES', 'Succès'),
        ('ECHEC', 'Échec'),
        ('EN_COURS', 'En cours'),
    ]
    type = models.CharField(
        max_length=15, choices=TYPES, default='AUTOMATIQUE'
    )
    statut = models.CharField(
        max_length=15, choices=STATUTS, default='EN_COURS'
    )
    fichier_db = models.CharField(max_length=200, blank=True)
    taille_mb = models.FloatField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sauvegarde'

    def __str__(self):
        return (
            f"Sauvegarde {self.get_type_display()} — "
            f"{self.created_at.strftime('%d/%m/%Y %H:%M')}"
        )