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
    type_ecole = models.CharField(max_length=10, choices=TYPES_ECOLE, default='PRIVE')
    systeme_defaut = models.CharField(
        max_length=15, choices=SYSTEMES, default='TRIMESTRIEL')
    region = models.CharField(max_length=100, blank=True)
    ministre_tutelle = models.CharField(max_length=200, blank=True)
    devise = models.CharField(
        max_length=100, blank=True, default='Travail – Liberté – Patrie')
    # Seuils alertes présences
    heure_rapport_directeur = models.TimeField(default='09:00')
    heure_rapport_censeur = models.TimeField(default='18:00')
    seuil_retards_consecutifs = models.IntegerField(default=5)
    seuil_retards_periode = models.IntegerField(default=10)
    seuil_jours_periode = models.IntegerField(default=20)
    # Finance
    seuil_alerte_dette_jours = models.IntegerField(default=30)
    # WhatsApp
    wa_numero_source = models.CharField(max_length=20, blank=True)
    wa_numero_secours = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuration école'

    def __str__(self): return self.nom

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SauvegardeAuto(models.Model):
    fichier = models.CharField(max_length=300)
    taille_ko = models.IntegerField(default=0)
    statut = models.CharField(
        max_length=10,
        choices=[('OK', 'Succès'), ('ERREUR', 'Erreur')],
        default='OK')
    message = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']